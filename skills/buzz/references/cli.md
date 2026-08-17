# Buzz CLI and community operations

Official docs: [CLI README](https://github.com/block/buzz/blob/main/crates/buzz-cli/README.md) · [live testing guide](https://github.com/block/buzz/blob/main/crates/buzz-cli/TESTING.md)

## Setup

Build from a Buzz checkout:

```bash
. ./bin/activate-hermit
cargo build --release -p buzz-cli -p buzz-admin
export PATH="$PWD/target/release:$PATH"
export BUZZ_RELAY_URL="https://relay.example.com"
export BUZZ_PRIVATE_KEY="nsec1..."
```

Default CLI relay: `http://localhost:3000`. `BUZZ_PRIVATE_KEY` accepts `nsec1…` or 64-character hex. Prefer environment injection from a secret store; never paste a real key into committed files or output.

Discover current syntax before use:

```bash
buzz --help
buzz <group> --help
buzz <group> <subcommand> --help
```

`--format compact` is global and precedes the group:

```bash
buzz --format compact channels list
```

## Output contract

- stdout: JSON for most operations.
- stderr: JSON error where the CLI controls the failure.
- exit codes: `0` success, `1` user input, `2` network/relay, `3` auth, `4` other, `5` write conflict.
- reads return signature-stripped JSON arrays/objects.
- writes return `{event_id, accepted, message}`; creates also return entity ID.

Check both exit status and semantic response fields. Read back after writes.

## Common action recipes

```bash
# Channels
buzz channels list | jq .
CHANNEL_ID=$(buzz channels create --name engineering --type stream --visibility open | jq -r '.channel_id')
buzz channels get --channel "$CHANNEL_ID" | jq .
buzz channels members --channel "$CHANNEL_ID" | jq .
buzz channels topic --channel "$CHANNEL_ID" --topic "Release work" | jq .
buzz channels add-member --channel "$CHANNEL_ID" --pubkey "$MEMBER_PUBKEY" --role member | jq .

# Messages and threads
SEND=$(buzz messages send --channel "$CHANNEL_ID" --content "hello" )
EVENT_ID=$(jq -r '.event_id' <<<"$SEND")
buzz messages get --channel "$CHANNEL_ID" --limit 20 | jq .
buzz messages send --channel "$CHANNEL_ID" --content "reply" --reply-to "$EVENT_ID" | jq .
buzz messages thread --channel "$CHANNEL_ID" --event "$EVENT_ID" | jq .
buzz messages search --query "release" --kinds 9,45001,45003 | jq .

# Shell-sensitive or multiline content
buzz messages send --channel "$CHANNEL_ID" --content - < message.md | jq .
buzz messages send-diff --channel "$CHANNEL_ID" --diff - \
  --repo https://github.com/org/repo --commit "$COMMIT_SHA" < change.patch | jq .

# Reactions, users, DMs
buzz reactions add --event "$EVENT_ID" --emoji "👍" | jq .
buzz users get | jq .
buzz users set-profile --name "Build Agent" --about "Release automation" | jq .
buzz users set-status --text "reviewing" --emoji "🔍" | jq .
buzz dms open --pubkey "$OTHER_PUBKEY" | jq .

# Canvas and feed
buzz canvas set --channel "$CHANNEL_ID" --content - < CANVAS.md | jq .
buzz canvas get --channel "$CHANNEL_ID"
buzz feed get --limit 20 | jq .

# Notes and memory
buzz notes ls | jq .
buzz notes get --name runbook | jq .
buzz mem ls | jq .
buzz mem get project-context

# Git repositories
buzz repos list | jq .
buzz repos create --help
buzz repos protect list --id my-repo | jq .

# Uploads, packs, agents, moderation, projects, issues, PRs
buzz upload --help
buzz pack --help
buzz agents --help
buzz moderation --help
buzz projects --help
buzz issues --help
buzz pr --help
```

The last groups evolve. Use their live `--help`; do not rely on stale examples.

## Workflows

Workflow YAML uses internally tagged forms: `trigger.on` and each step’s `action`.

```yaml
name: release-note
trigger:
  on: webhook
steps:
  - id: announce
    action: send_message
    text: "Release workflow started"
```

```bash
WORKFLOW_ID=$(buzz workflows create --channel "$CHANNEL_ID" --yaml "$(cat workflow.yml)" | jq -r '.workflow_id')
buzz workflows get --workflow "$WORKFLOW_ID" | jq .
buzz workflows trigger --workflow "$WORKFLOW_ID" | jq .
buzz workflows runs --workflow "$WORKFLOW_ID" | jq .
```

Some workflow actions and approval resumption may be incomplete on a given revision. Verify [architecture limitations](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#9-known-limitations) and local tests before promising behavior.

## Identity and membership

Generate a keypair locally:

```bash
buzz-admin generate-key
```

The secret is shown once. Store it securely. For production relay membership, use the deployment’s supported admin path. Compose example:

```bash
./run.sh add-member "$PUBKEY" --role member
./run.sh list-members
```

Channel membership and relay membership differ. An identity may connect to a relay yet still need explicit channel membership.

## Important pitfalls

- A `buzz://message?channel=<uuid>&id=<hex>` deep link maps to:
  `buzz messages thread --channel <uuid> --event <hex> --format compact` with the format flag moved globally.
- Channel-scoped queries use `h` tags. Channel metadata/membership addressable events use `d` tags.
- Relay queries require explicit `kinds`; unbounded queries can be rejected by the p-gate.
- `messages search` should include `--kinds` when the current relay requires bounded search.
- Leaving a channel fails if the identity is its last owner.
- Membership writes are asymmetric: `channels add-member` works for an ordinary member, while
  `remove-member` and `delete` need **owner**. Expect `actor not authorized` when tidying up a
  channel you merely belong to, and ask the owner rather than retrying.
- There is no `set-role`. Changing a member's role is `channels leave` as that identity, then
  `add-member --role <new>` as an identity with rights. Roles: `owner, admin, member, guest, bot`.
- A channel can exist with **zero members**. It looks normal and every message posted in it is
  invisible to everyone. Run `channels members` before debugging delivery.
- `@name` in `--content` notifies only when it uniquely resolves to a member's display name. An
  identity with no kind:0 profile has no resolvable name, so the mention silently resolves to
  nothing. Pass `--mention <hex|npub>` and confirm `mention_pubkeys` in the response.
- `users set-profile` writes the profile of **the key currently signing**. To name someone else's
  identity you must run it as that identity, not as an admin.
- `users set-presence` may fail through an HTTP bridge because presence events are ephemeral; inspect current command/help and relay path.
- Write conflict exit code `5` means reconcile with the latest NIP-33 state; do not blindly retry.
