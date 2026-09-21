# Maintaining this skill

Follow this when refreshing the skill against the live docs. The design rule
that makes the refresh cheap: **SKILL.md holds only judgment that outlives a
model release**, and every example, field shape, price, and limit stays in the
docs. A refresh therefore edits the few pinned facts listed below and re-checks
the judgment against its source pages — it never copies examples in.

## State at last refresh

| | |
| --- | --- |
| Refreshed on | 2026-09-21 |
| Docs pages in `llms.txt` at that time | 110 links |
| Current model | `jev-1.13.0`, reached by the `jev-latest` and `jev-preview` aliases |
| Jaggedness page then | `/model-jaggedness/jev-1.13`, itself stamped "Last reviewed 2026-09-17" |
| Verified live | `POST https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer $TYPESAFE_AI_API_KEY` returned `200` and the response fields the docs describe (`model`, `answers`, `usage`; `noul`; `choice` + `probabilities` + `confidence`; `score` + `legend` + `probabilities` + `confidence`) |
| Env var checked | `TYPESAFE_AI_API_KEY` is set here; `TYPESAFE_API_KEY` is not. The SDKs read `TYPESAFE_API_KEY` |

## Detect drift

Run these; each one points at what to re-read.

1. **New, renamed, or removed pages** — the page inventory:
   ```bash
   curl -sL https://docs.typesafe.ai/llms.txt | grep -c 'docs.typesafe.ai'   # link count
   curl -sL https://docs.typesafe.ai/llms.txt | grep -oP '(?<=\()https://[^)]+' | sort
   ```
   Compare against the tables in `doc-map.md`. New concept, pattern, or cookbook
   pages belong in the map; a renamed path breaks a row.

2. **Pages edited since the refresh date** — the sitemap carries `lastmod`:
   ```bash
   curl -sL https://docs.typesafe.ai/sitemap.xml \
     | grep -oP '<loc>\K[^<]+|<lastmod>\K[^<]+' | paste - - | sort -k2
   ```
   Any core page (see the provenance table) with a `lastmod` after the refresh
   date gets re-read.

3. **A new model version** — this is the highest-value check, because the
   jaggedness list is per version and the SKILL.md table mirrors it:
   ```bash
   curl -sL https://docs.typesafe.ai/models.md | grep -iE 'jev-|alias'
   ```
   When `jev-latest` points somewhere new, find the new jaggedness page in
   `llms.txt`, re-read it, and rewrite the "Jagged edges" table and the
   `doc-map.md` row from it. Confidence thresholds anywhere in the user's code
   were tuned against the old version — flag that to the user.

4. **Contract or SDK change** — re-read `/api.md` plus the SDK changelogs
   (`/sdk/python/changelog`, `/sdk/javascript/changelog`). A breaking SDK
   release changes the install names, client names, or typed accessors named in
   SKILL.md § Local setup.

5. **Live smoke check** — one cheap request confirms the endpoint, auth header,
   and answer fields still match the docs:
   ```bash
   curl -s -X POST https://api.typesafe.ai/v1/systemone \
     -H "Authorization: Bearer $TYPESAFE_AI_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"state":"test","model":"jev-latest","questions":{"q":{"type":"noul","instructions":"Is this a test?"}}}'
   ```

6. **TypeSafe's own official skill** — worth diffing for guidance that changed
   upstream: `https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md`.

## Provenance: which claim came from which page

Re-read the right-hand page to re-verify the left-hand section.

| SKILL.md section | Source pages |
| --- | --- |
| Framing; what Jev is and is not | `/introduction`, `/concepts/system-one`, `/introduction/coding-agents` |
| Live-docs rule and `.md` mechanics | `/agent-skill`, and the index banner on every `.md` page |
| Reach for Jev where code needs meaning | `/concepts/how-to-build-with-system-one`, `/concepts/use-case-map`, the cookbook index |
| Pick the primitive; Choice-vs-Noul absolute/relative | `/primitives`, `/primitives/choice`, `/primitives/score`, `/primitives/noul`, `/model-jaggedness/jev-1.13` § Common-sense structural invariants |
| Shape the state | `/concepts/state`, `/primitives` § Reference specific fields, `/model-jaggedness/jev-1.13` § Large state, `/models` § Language support |
| Write the questions | `/primitives`, `/primitives/score` § Writing good levels, `/primitives/noul` § Writing a Noul question, `/primitives/advanced`, `/model-jaggedness/jev-1.13` §§ Literal reading, Contradictory instructions |
| One request, many questions | `/primitives` § Ask multiple questions together, `/patterns/fan-out`, `/cookbooks/parallel_questions` |
| Compose in code | `/concepts/how-to-build-with-system-one`, `/patterns/composite-scoring`, `/primitives/score` § Splitting a complex judgment |
| Gate on confidence | `/confidence`, `/patterns/confidence-routing`, `/models` § Aliases, `/agent-skill` § Common issues |
| Jagged edges table | `/model-jaggedness/jev-1.13` — one row per failure mode on that page |
| Make it reviewable | `/agent-skill` §§ Good vibe coding principles, Common issues |
| Local setup | `/sdk/python`, `/sdk/javascript`, `/models` (rate limits and retries), `/api` § Handling rate limits, plus the local env check above |
| Validate before shipping | `/confidence` (tune on your own data), `/models`, `/agent-skill` |

## Numbers pinned in SKILL.md and doc-map.md

These are the only version-dependent values written down. Re-check each on a
refresh; everything else is fetched at use time.

| Value | Where it appears | Source |
| --- | --- | --- |
| 255 options per Choice | `doc-map.md` Choice row | `/api` § Choice `criteria`, `/primitives/choice` |
| 2–10 Score levels | `doc-map.md` Score row | `/api` § Score `criteria`, `/primitives/score` |
| Python ≥ 3.10, Node ≥ 20, `typesafe-sdk`, `@typesafe-ai/sdk` | SKILL.md § Local setup | `/sdk/python`, `/sdk/javascript` |
| `429` / `529` retried with backoff by default | SKILL.md § Local setup | `/models`, `/api` § Handling rate limits |
| Endpoint `POST https://api.typesafe.ai/v1/systemone` | SKILL.md § Local setup (implicit), this file | `/api` |
| `jev-1.13` jaggedness page path | SKILL.md § The live docs, § Jagged edges; `doc-map.md` | `/models` alias table |

Context length, price, and rate-limit numbers are deliberately **not** written
into SKILL.md — they change without notice, and `/models` is one fetch away.

## When editing, keep the shape

- Judgment in, examples out. A request or response example in SKILL.md is the
  failure this design exists to prevent: it goes stale silently and the agent
  invents fields from it. Point at the page instead.
- One meaning in one place. The jagged-edges table lives only in SKILL.md; the
  cookbook index lives only in `doc-map.md`.
- Update `version:` in the SKILL.md frontmatter and the refresh date above in
  the same edit, so a reader can tell how old the pinned facts are.
