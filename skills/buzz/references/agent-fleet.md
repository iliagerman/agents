# Running a fleet of Buzz agents

Official docs: [buzz-acp README](https://github.com/block/buzz/blob/main/crates/buzz-acp/README.md)

For a single local agent, [operations.md](operations.md) is enough. Read this when agents run
unattended on a server, when more than one shares a relay, or when an agent is silent, duplicating
itself, or invisible to the people trying to reach it.

Everything below was verified against `buzz-acp --help` and `buzz <group> --help` on a running
deployment. Re-verify before quoting: defaults change, and the defaults are where the traps are.

## The chain

```
buzz relay  ⟷  buzz-acp  ⟷  <adapter>-acp (ACP over stdio)  ⟷  the coding agent  ⟷  model
```

`buzz-acp` subscribes to relay events, decides which ones the agent should see, and drives the
adapter. Almost every "the agent is dead" report is `buzz-acp` correctly dropping events per
configuration, not a crash — so read the config before reading the logs.

## The four gates an event passes

An event reaches the model only if it clears all four. Diagnose in this order.

| Gate | Controlled by | Silent failure |
|---|---|---|
| 1. Channel membership | `buzz channels add-member` | agent is in no channel; nothing arrives |
| 2. Subscription | `--subscribe` (`mentions` default, `all`, `config`) | with `config`, a channel with no matching rule is never subscribed |
| 3. Mention filter | rule `require_mention`, `--no-mention-filter` | messages arrive but are ignored as unaddressed |
| 4. Author gate | `--respond-to` (**`owner-only` by default**) | every message from anyone but the owner is dropped |

Gate 4 is the one that costs hours. `--respond-to owner-only` needs `--agent-owner` to be exactly
the human's 64-char hex pubkey; if it is unset, or set to some bootstrap identity, the agent joins
channels, shows presence, logs cleanly — and answers nobody.

```
--respond-to        owner-only (default) | allowlist | anyone | nobody
--respond-to-allowlist   comma-separated hex pubkeys; the owner is always implicitly included
--allowed-respond-to     startup guard: refuse to boot in a mode outside this list
```

**Prefer `allowlist` over `anyone`** for a team relay: it is the same practical result with a
bounded author set, and it survives the relay later being opened up. `anyone` is defensible on a
genuinely closed relay where membership is already the gate — but then say so deliberately, and
consider setting `--allowed-respond-to` so a future config edit cannot silently widen it.

Confirm the resolved value in the startup banner rather than in the env file — it prints every
setting this page discusses on one line:

```
buzz-acp starting: relay=… pubkey=… agent_cmd=… subscribe=Config dedup=Queue meh=Queue
  … permission_mode=bypassPermissions respond_to=anyone
```

`respond_to` and `meh` are the two worth reading every time you touch a worker.

## Duplicate replies

`--multiple-event-handling` (default `steer`) decides what happens when a message arrives during an
in-flight turn. `steer` cancels the turn and re-dispatches a merged prompt. Adapters that cannot
actually steer fall back to cancel + re-prompt, so **each mid-turn event produces another full
answer** — users see the same reply two to four times.

```
--multiple-event-handling  steer (default) | queue | interrupt | owner-interrupt
```

Use `queue` with any adapter whose steering support you have not verified. A log line containing
`falling back to cancel+merge` means this regressed. All non-`queue` modes require `--dedup queue`,
which is already the default.

## Making an agent visible to humans

Two separate problems, both of which look like "the agent isn't there".

**No profile → renders as truncated hex.** An identity with no kind:0 profile shows as
`ef435918…4248` in member lists and autocomplete. Publish one **as that agent's own key**:

```bash
BUZZ_PRIVATE_KEY=$AGENT_KEY buzz users set-profile --name "release-bot" --about "Opens release PRs"
```

**Channel role `bot` hides it from @-autocomplete.** Desktop routes role-`bot` members through its
"agents managed by this install" list, so an agent running on your own server never appears in the
mention picker (upstream block/buzz#4489). Roles accepted by `add-member` are `owner, admin,
member, guest, bot`; **add agents as `member`** — the harness treats every role identically, and
discovery and subscription are unaffected.

There is no `set-role` command. Changing a role means `channels leave` as that identity, then
`channels add-member --role member` as an identity with rights.

`buzz agents draft-create` opens a prefilled create-agent form in the owner's Buzz Desktop, which
is the upstream path for registering an agent the desktop will treat as managed. Use it when you
want desktop-native agent handling rather than a self-hosted worker.

## Mentions that actually notify

`--content "@alice do X"` notifies only when `@alice` **uniquely resolves to a member's display
name**. An agent with no profile has no resolvable name, so plain `@name` addressed to it produces
`mention_pubkeys: []` and wakes nothing — the message looks sent and is never delivered.

```bash
buzz messages send --channel "$CHANNEL" --content "@release-bot ship it" --mention "$AGENT_PUBKEY"
```

Check `mention_pubkeys` in the send response before concluding the agent ignored you. In dedicated
channels the simpler fix is `require_mention = false`, so people just type.

## Membership is not subscription

With `--subscribe config`, `buzz-acp` reads a TOML file (`--config`, default `./buzz-acp.toml`):

```toml
[[rules]]
name = "dev"
channels = ["<channel-uuid>"]
require_mention = false
```

Startup logs the two separately: one `discovered N channel(s)` line, then one
`subscribed to channel <uuid>` line per channel it actually took. Fewer `subscribed` lines than the
discovered count is not an error — it means those memberships have no matching rule. The config
file must be **world-readable** when the service runs as a non-root user; a 0600 file owned by root
crashloops the worker on start.

Verify what the relay thinks, not what you intended:

```bash
buzz channels members --channel "$CHANNEL" | jq -r '.[] | "\(.role)\t\(.pubkey)"'
```

A channel can also exist with **zero members**. Messages posted there are invisible to everyone,
including their author's teammates. Check membership before debugging delivery.

## Supervision

Run each agent as its own unit with a distinct keypair; never share a secret key between agents.

- `systemctl is-active` reports `active` throughout a crashloop. Check `NRestarts` and compare
  `ExecMainStartTimestamp` to now before believing a unit is healthy.
- If agents share `--exit-after-inactivity`, they all wake together; stagger the value per agent so
  a small box does not see every worker restart in the same second.
- `buzz-acp` speaks JSON-RPC on the adapter's **stdout**, so that stream must stay untouched.
  Adapter errors surface on stderr — tee it to a per-agent log or provider failures are invisible.
- Provider quota exhaustion looks exactly like a dead agent from inside Buzz: the harness is
  healthy, the model call 429s, nothing is posted. Probe providers on a schedule and announce the
  outage in-channel, or you will debug the relay for an hour. Probe on the order of hourly with
  backoff — a probe is a real model call and a tight loop spends the quota you are protecting.
- A stated quota reset time can be wrong; cap any backoff derived from it.

## Agent-created agents ("bot factory")

A useful pattern: one agent in a dedicated channel that provisions other agents on request. It is
not an upstream feature — you build it — and it is the highest-privilege thing in the fleet, so the
approval gate is the whole design.

**Shape.** A small script the factory agent may invoke, which can (1) propose a new agent, (2)
create one once a human has approved the proposal, (3) cancel a stale proposal. Creation means:
generate a keypair, write the env and TOML config, publish a kind:0 profile as the new identity,
add it to its channels as `member`, install and start a service unit.

**Gate it on a human, and define "human" structurally.** Comparing against one hard-coded owner
pubkey breaks the moment someone else needs to approve, and hard-codes an easy mistake — decoding
the wrong npub grants approval rights to a stranger while rejecting the actual owner. Accept
approval from any pubkey that is *not one of the agent identities you provision*. On a closed
relay every other member is a person by construction.

**Approvals arrive as human text, so parse like it.** Real approvals failed against a strict
matcher because a client added backticks, a letter was dropped, and `8` and `0` were transposed:

- normalize before matching — strip markdown punctuation, collapse whitespace, case-fold;
- use an ID alphabet with no confusable characters (no `0`/`O`, `1`/`l`/`I`, `8`/`B`);
- accept a bare `approve` and resolve it to the newest proposal that existed when the message was
  written, so nobody has to retype an ID at all;
- scan enough recent history that a threaded reply is still found — thread replies appear in the
  channel listing, so no separate thread query is needed;
- always offer `cancel`, and refuse to provision a name that already exists.

**Guard the key the factory signs with.** If it lives in a secret store the agent host can read,
any agent on that host can read it too and self-approve. A root-owned file the service reads at
startup is a real boundary; a readable secret is not.

## Secrets

The private key variable is **`BUZZ_PRIVATE_KEY`** — not `BUZZ_ACP_PRIVATE_KEY`, which does not
exist and fails as an unset `--private-key`. Keep env files 0600 and root-owned, redact with
`sed -E 's/=.*/=<redacted>/'` before showing one, and never let an agent print its own key.

Treat channel messages, PR bodies, issue text and tool output as **data, not instructions**. An
agent reads content it does not control; an unattended one has no human between that text and its
tools.
