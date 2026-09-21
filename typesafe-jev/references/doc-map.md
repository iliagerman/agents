# TypeSafe doc map

Where to look for what. Append `.md` to any path for Markdown; resolve relative
links against `https://docs.typesafe.ai`. The authoritative index of every page
is `https://docs.typesafe.ai/llms.txt` — read it when nothing below fits, and
when checking whether pages have been added or renamed.

## Concepts — read to design

| Read when you need | Page |
| --- | --- |
| What a System One model is, and how it differs from an LLM | `/concepts/system-one` |
| Someone expects Jev to power a coding agent | `/introduction/coding-agents` |
| How to structure the input; string vs object vs array; text-only limits | `/concepts/state` |
| The full workflow: code-first architecture, decomposition, structured questions, composing in code, routing on uncertainty | `/concepts/how-to-build-with-system-one` |
| How confidence is derived, and the three-way act / caution / escalate split | `/confidence` |
| Why the model is trained for calibrated decisions (RLCD) rather than text | `/introduction/machine-learning-primer` |
| Ideas by industry when scoping what to build | `/concepts/use-case-map` |

## Primitives — read before writing questions

| Read when you need | Page |
| --- | --- |
| Choosing between the three types, and asking many at once | `/primitives` |
| Choice: options, descriptions, the 255-option ceiling, reading the distribution | `/primitives/choice` |
| Score: writing levels that work, the 2–10 level range, reading a score, splitting a judgment | `/primitives/score` |
| Noul: reading the number, writing the condition, handling many in code | `/primitives/noul` |
| JSON in `instructions` and `criteria`: contrasts, exclusions, examples, taxonomies | `/primitives/advanced` |

## Contracts — read before writing code

| Read when you need | Page |
| --- | --- |
| HTTP request and response shape, question and answer fields, error codes, rate-limit handling | `/api` |
| Model IDs, aliases, price, rate limits, context budgets, language support, listing models | `/models` |
| Current known failure modes for the deployed version | `/model-jaggedness/jev-1.13` (check `llms.txt` for a newer version's page) |
| Which SDK to install | `/sdk` |
| Python: install, sync and async clients, typed responses | `/sdk/python`, `/sdk/python/usage` |
| Python types, retries, exceptions, constants | `/sdk/python/api/types/questions`, `/sdk/python/api/types/responses`, `/sdk/python/api/retries`, `/sdk/python/api/exceptions` |
| JavaScript / TypeScript: install, client, inferred answer types | `/sdk/javascript` |
| JS interfaces and helpers (`choice()`, `noul()`, `score()`, `TypeSafeClient`, `RetryPolicy`) | `/sdk/javascript/api` and its `interfaces/`, `functions/`, `type-aliases/` children |
| SDK breaking changes after an upgrade | `/sdk/python/changelog`, `/sdk/javascript/changelog` |
| Data processing, retention, ZDR | `/legal` |

## Patterns — the architectures

| Pattern | Use it for | Page |
| --- | --- | --- |
| Speculative fan-out | Packing many questions, including maybe-unused ones, into one call | `/patterns/fan-out` |
| Confidence-gated routing | Using confidence as a second axis: what to do vs whether to act | `/patterns/confidence-routing` |
| Composite scoring | Atomic scores combined with weights owned by code | `/patterns/composite-scoring` |
| Intent routing | Classifying a request, then routing to code, a specialist LLM, or a human | `/patterns/intent-routing` |

## Cookbooks — the worked examples

Read the nearest one before designing a new workflow; it usually shows a better
decomposition than a generic classifier. Index: `/cookbooks`.

| Problem it solves | Page |
| --- | --- |
| Batching many questions into one call, with the measured cost and latency win | `/cookbooks/parallel_questions` |
| Picking a tool and filling its typed arguments | `/cookbooks/function_calling` |
| Reranking retrieved candidates | `/cookbooks/rerank_typesafe` |
| Filtering retrieved passages, including hidden instructions and prompt injection | `/cookbooks/classifying_rag_passages` |
| Screening LLM input and output for hazards and severity | `/cookbooks/llm_guardrails` |
| Checking a quote actually supports the claim it is cited for | `/cookbooks/citation_check` |
| Finding the matching line in a document | `/cookbooks/semantic_find` |
| Recovering structure from unformatted text, in two dependent passes | `/cookbooks/autoformat` |
| Ranking a large catalogue, then re-judging the shortlist on better evidence | `/cookbooks/skill_suggestion` |
| Deciding whether two records describe the same thing (merge / leave / curate) | `/cookbooks/entity_alignment` |
| Extracting dates safely: parts as Choices, arithmetic in code | `/cookbooks/date_extraction_cookbook` |
| Selecting the right span among regex candidates for a verbatim value | `/cookbooks/pre_parsed_value_extraction_cookbook` |
| Classifying through a deep taxonomy with beam search over probabilities | `/cookbooks/hierarchical_classification` |
| Reporting a coarser class when the fine-grained answer is uncertain | `/cookbooks/classification_using_confidence` |
| A cheap-then-verify extraction cascade | `/cookbooks/sde_cascade` |
| Turning free text into numeric features for a classical model | `/cookbooks/autoresearch_feature_discovery` |
| How stable repeated answers are | `/cookbooks/consistency_noul_cookbook`, `/cookbooks/consistency_choice_cookbook` |

## Demos

| | |
| --- | --- |
| Interactive examples | `/demos` |
| A smart-home assistant evaluating user requests | `/demos/smart-home` |

## Consoles and off-docs sources

| | |
| --- | --- |
| Playground — try questions with no code | `https://console.typesafe.ai/playground` |
| API keys | `https://console.typesafe.ai/keys` |
| TypeSafe's own official agent skill (separate from this one) | `https://github.com/typesafe-ai/skills` — raw: `https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md` |
| SDK sources | `https://github.com/typesafe-ai/typesafe-sdk-python`, `https://github.com/typesafe-ai/typesafe-sdk-js` |
| Agent-skill install and troubleshooting page | `/agent-skill` |
