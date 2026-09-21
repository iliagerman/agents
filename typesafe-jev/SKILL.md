---
name: typesafe-jev
description: Build on TypeSafe's Jev (System One) API — typed judgments with calibrated probabilities and confidence, asked as Choice, Score and Noul questions. Use when code touches typesafe_sdk, @typesafe-ai/sdk or api.typesafe.ai; when designing routing, classification, scoring, ranking, guardrails, verification, or extraction-by-selection; or when a prompt-and-parse "return JSON" LLM call, a hand-tuned regex heuristic, or a bespoke classifier should become a structured decision. Carries judgment only — every example, field shape and limit is fetched from the live docs.
version: 1.0.0
homepage: https://docs.typesafe.ai
metadata:
  {
    "ilia":
      {
        "emoji": "🎯",
        "requires": { "env": ["TYPESAFE_AI_API_KEY"] },
        "primaryEnv": "TYPESAFE_AI_API_KEY",
      },
  }
---

# Build with TypeSafe (Jev)

Jev is a **System One** model: it returns typed judgments and calibrated probabilities instead of text. Code owns the control flow and every exact computation; Jev supplies programmable common sense at the points where code has to read meaning. It writes no text, holds no conversation, and cannot power a coding agent — there is no setting that turns Claude Code or Cursor into "Jev mode". You use a coding agent to write code that calls Jev.

## The live docs are the source of truth

This skill carries judgment: what to reach for, how to shape it, what Jev is bad at. Everything version-dependent — request and response field shapes, worked examples, prices, rate limits, context budgets, SDK signatures, cookbooks — lives in the docs and is **fetched in the same task that uses it**. An integration written from memory is how invented request fields get shipped.

Mechanics:

- Append `.md` to any docs path for clean Markdown: `https://docs.typesafe.ai/api.md`.
- The index of every page is `https://docs.typesafe.ai/llms.txt`. Read it to find a page this skill does not name.
- Resolve a page's relative links against `https://docs.typesafe.ai`.
- [`references/doc-map.md`](references/doc-map.md) maps each question you might have to the page that answers it, and lists every cookbook with the problem it solves.

**Before writing integration code**, read in this order:

1. `/api.md` for HTTP, or `/sdk/python.md` / `/sdk/javascript.md` for an SDK — the exact request and response shape, and the SDK's typed constructors.
2. The page for each primitive in the design: `/primitives/choice.md`, `/primitives/score.md`, `/primitives/noul.md`.
3. `/model-jaggedness/jev-1.13.md` — the current known failure modes. Re-read it every time; the list is per model version and moves.
4. The nearest cookbook from `references/doc-map.md`. A cookbook usually shows a sharper decomposition than a generic classifier would.

When the docs are unreachable, say so plainly, fall back to the installed SDK's own types, and leave version-dependent details unstated rather than guessed.

## Reach for Jev where code needs meaning

Each shape below is a starting point, not a boundary. Combine primitives around the goal.

- **Route, and fill the arguments.** One request picks the handler and the typed parameters it needs. Ask the branch-specific questions up front; code consumes only the branch it took.
- **Select instead of generate.** Find candidate values or source spans in code (regex, parser, retrieval), let Jev pick the intended one, then copy or normalize it in code. Jev is not trained to generate, so bounded extraction beats free-form extraction.
- **Find and judge evidence.** Retrieve candidates, judge each one's relevance, and let code decide what reaches the answering model or the user.
- **Turn judgments into reusable data.** Score the dimensions once; weights, thresholds, rankings, and views then change in code without new inference. With labeled outcomes those probabilities become features for a classical model.
- **Verify and escalate.** Check a specific claim or field against its evidence, and send the uncertain cases to a person or a reasoning model.
- **Guard a boundary.** Screen what enters and leaves an LLM: hazards as Nouls, severity as a Score, and the pass / review / block decision in code.

## Pick the primitive by what the answer means

| Need | Primitive | The distinction that decides it |
| --- | --- | --- |
| One of a defined set | **Choice** | Picks one option; the distribution is *relative* — it compares your options against each other |
| Degree along one described dimension | **Score** | Probability-weighted position across ordered levels; can land between levels |
| Whether a condition holds | **Noul** | *Absolute* probability that yes is true; carries no separate confidence |

Prefer the type whose answer code can act on directly: a Choice maps onto branches, a Score onto a threshold, a Noul onto an `if`.

A Noul of 0.5 means yes and no are equally likely — it never means "medium". For degree ("how strong is this candidate?"), use a Score with described levels. For a clean boundary ("does the resume state paid Python work?"), use a Noul.

A Choice over N options and N one-per-option Nouls answer different questions. The Choice settles *which*; each Noul can be low for all of them. Use both together when you need to pick one and also decide whether to act at all.

## Shape the state

- Send **only what the questions need**. Accuracy falls as irrelevant content grows — retrieve and filter in code first. When filtering in code is impossible, use a Noul to judge relevance and drop the rest.
- Prefer a **JSON object with named fields** once the state has several parts (message, record, policy). A plain string is right only when there is one piece of text.
- Point a question at a part of the state with a **backticked path**: `` `ticket.messages[0].text` ``. Explicit paths tell the model which part to judge.
- Related parts belong in one state when the judgment compares them. A conversation, the order it refers to, and the governing policy are one state.
- Text only. Convert images, audio, and binaries to text or structured fields before sending. English is strongest; test other languages on your own content.

## Write the questions

- **One snap judgment per question.** The bar: a judgment a knowledgeable person makes in a second given the right context. If answering needs extended reasoning or weighs independent factors, split it and combine in code.
- **Write the exact condition.** Jev answers the question you wrote, not the one you meant — scoping words, negations, and implied conditions are read at face value. When a wrong answer makes you explain what you really meant, that explanation is the missing half of the instruction.
- **Criteria are an extension of the instruction.** Keep them aligned and plainly worded. A Noul whose `true` description means no will perform worse.
- **Describe situations, not degrees.** Score levels like "broken feature, workaround exists" give the model something to match; "moderately severe" and bare numbers do not. Each level is judged alone — it never sees its neighbours or its number, so "worse than the last level" means nothing.
- **One dimension per Score.** A level describing three qualities at once cannot place an input that is high on one and low on another.
- **Give the answer somewhere to go.** Add an `other` / `none of the above` option when the list may not cover every input, and give a rare extreme its own level when you act on it differently. For select-from-candidates, check candidate coverage: the model cannot pick a value that was never offered.
- **Phrase a Noul so that high means yes.** Ask one condition per Noul; two conditions in one question make the number mean less.
- **Question IDs never reach the model.** Put the complete meaning in `instructions`, however self-explanatory the key looks.
- **Reach for JSON in `instructions` and `criteria`** when a question has several parts, carries a record or taxonomy, or needs contrasts and exclusions per option. Start with strings; structure when strings get cramped.

## One request, many questions

Every question that shares a state goes in **one request**. Questions are evaluated in parallel and in isolation, so adding them barely moves latency, costs only their own tokens, and creates no context rot. Batching is dramatically cheaper and faster than one call per question.

Ask **speculative** questions too — ones whose answers only matter for some inputs — and let code ignore the rest. State each speculative premise explicitly in its own instruction, since no question can see another's answer.

A second request is warranted only when code **cannot build it** until the first answer lands: it needs that answer to fetch evidence, to assemble new state, or to choose the next question's options. Otherwise, ask everything up front. Coding agents default to one-question-per-call; resist it.

## Compose in code

- Combine answers with **explicit weights and thresholds** that live in code. When the combined result disagrees with what your team would decide, change a coefficient — not a prompt.
- Weighted sums fit compensating preferences. "Any serious violation blocks" is a separate condition, not a weight.
- Keep the **raw judgments reusable**: changing a weight, filter, or display rule needs no new inference while the evidence and question meanings hold.
- Typed output guarantees the interface, not the truth. Calibration is a property of groups of predictions; it never promises one answer is right.

## Gate on confidence

Choice and Score answers carry `confidence` in 0–1, derived from how peaked `probabilities` is. A useful starting split:

- **High** — act automatically.
- **Medium** — confirm with the user, flag for review, or gather more evidence.
- **Low** — do not act: route to a person, ask for clarification, or fall back.

Thresholds scale with the stakes: a destructive action earns a higher bar than a read-only one, in the same system. Tune every threshold on your own data and consequences — no number here is a default to ship.

Confidence summarizes distribution shape, not workflow correctness and not permission to act. Several acceptable options also spread probability, so low confidence on a harmless preference is fine. Ignore uncertainty on branches you did not take. When you only need the best option, take the top one rather than thresholding at all; when you have a specific statistical algorithm in mind, work from `probabilities` directly.

Thresholds tuned against one model version belong with a pinned version ID, not an alias — an alias moves when a release ships. Log the `model` field the response reports.

## Jagged edges: keep these in code

Jev is jagged. Confirm the current list in `/model-jaggedness/jev-1.13.md`, and design around it:

| Jagged edge | Do this instead |
| --- | --- |
| Arithmetic, counting, interpolating a magnitude between Score levels | Compute in code. To count matches, ask one question per candidate and sum the answers yourself |
| Date and time ordering, distance, windows | Extract the parts as Choices over closed sets (months, days, years, plus an explicit "not stated"), then assemble and compare in code |
| Numeric and low-level representations (hex, RGB, assembly, binary) | Convert in code; hand the model the named bucket or the semantic question |
| Indirection — double negatives, a property of a property, multi-hop reasoning | Write the instruction directly and name the relevant state by path |
| Large state padded with irrelevant detail | Filter first, or gate relevance with a Noul |
| Adversarial state that argues for its own classification | State is data, not hostile by default: be explicit in criteria and test edge cases before rollout |
| Structural invariants you would expect to hold | Don't rely on them. A Noul threshold does not carry over to a Choice, and `P(x)` and `1 − P(not x)` need not agree |
| Generating text | Use a generative model, or bound the answer space and select |

## Make it reviewable

Put every question and every threshold in **one constants file**. Humans review the questions and the numbers, and that review is the point — it should not require spelunking through the codebase. Agents are weak question writers, so expect to edit them with the user rather than for them.

## Local setup

- The API key is in **`TYPESAFE_AI_API_KEY`** in this environment, but both SDKs and the docs' examples read **`TYPESAFE_API_KEY`**. Either pass the key to the client explicitly, or export `TYPESAFE_API_KEY="$TYPESAFE_AI_API_KEY"` for the process. Confirm the env var name on the SDK page — never print the value.
- Keys: `https://console.typesafe.ai/keys`. Playground for trying questions with no code: `https://console.typesafe.ai/playground`.
- Install names: `typesafe-sdk` (Python, ≥3.10), `@typesafe-ai/sdk` (Node ≥20). Both retry `429` and `529` with backoff by default; calling the HTTP API directly means owning that backoff.
- Keep the key server-side in anything a browser touches.

## Validate before shipping

Run cheap real requests against representative cases — the key is already in the environment — and check the resulting application behavior, not just the answers. When one is wrong, separate the causes: missing evidence, a question that says the wrong thing, a code error, or a service failure. Inspect the exact state, questions, candidates, answers, and composition before changing anything.

Treat every cookbook threshold and benchmark as an example to evaluate on your own data, never as a universal rule or a permanent model limit.

## Updating this skill

When the docs move, or on request to refresh this skill, follow [`references/maintenance.md`](references/maintenance.md). It records which claims here are version-pinned, the page each one came from, and the checks that detect drift.
