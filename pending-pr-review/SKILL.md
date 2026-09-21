---
name: pending-pr-review
description: Walk through an open GitHub PR or pending GitHub pull request for architectural review, usually as an interactive paced conversation rather than a full report dump. Use this whenever the user asks to review, walk through, explain, evaluate, or understand a GitHub PR by number or URL, especially phrases like "walk me through PR #37", "review this pending PR", "explain the main decisions", "pros and cons", "architecture review", or "should we merge this PR". This skill focuses on design choices, architecture, alternatives, risks, and reviewer insight rather than low-level code commentary.
---

# Pending PR Review

Use this skill to help the user review an open GitHub pull request as a software architect. The goal is a conversational walkthrough that explains the big picture, identifies the main design decisions, weighs pros and cons, suggests alternatives, and gives the agent's own review insights.

The user is technically strong and wants architectural judgment, but they still value plain-English framing before technical detail.

## Scope

Review GitHub PRs only. Use the GitHub CLI (`gh`) and git commands to inspect the PR. This skill also applies when the user says "pending changes" but clearly refers to a GitHub PR.

Do not turn the review into a line-by-line code review unless the user explicitly asks. Mention code details only when they are important evidence for an architectural or design point.

## Workflow

1. Identify the PR number or URL from the user request.
2. Inspect PR metadata:
   - `gh pr view <PR> --json number,title,author,baseRefName,headRefName,body,createdAt,updatedAt,isDraft,reviewDecision,mergeStateStatus,statusCheckRollup,url`
3. Inspect changed files and diff:
   - `gh pr diff <PR> --name-only`
   - `gh pr diff <PR>`
4. If needed, inspect the repository rules and conventions before judging the PR:
   - Project `AGENTS.md` files, starting from the repo root and relevant subdirectories.
   - Local Claude/project rules when available.
   - Global rules when available, but treat local repo rules as more important.
   - Existing nearby code patterns that the PR should align with.
5. Build a mental model of the PR:
   - What problem it solves.
   - What systems/components it touches.
   - What architectural choices it makes.
   - What behavior changes for users/operators/developers.
6. Produce the review as a conversational walkthrough, not a dry checklist.

## Review emphasis

Prioritize:

- Architecture and design choices.
- Authentication, authorization, security, and tenant boundaries when relevant.
- Integration boundaries and external provider assumptions.
- Maintainability and extensibility.
- Configuration and operational impact.
- Backward compatibility and migration/deployment concerns.
- Test strategy and documentation impact.
- Consistency with existing repo patterns and local rules.

De-emphasize:

- Minor style issues.
- Formatting nits.
- Exhaustive code-level walkthroughs.
- Generic praise without evidence.

## Walkthrough pacing

Default to an interactive walkthrough, not a full report dump.

When the user says "walk me through", "let's review", "review this PR", "explain the decisions", or similar, start with only:

1. A 3-5 line plain-English big-picture summary.
2. A short list of the 3-5 main design decisions you found.
3. A suggested order for reviewing them.
4. A prompt asking whether to continue with the first decision or jump to a different one.

Then review one design decision per response. For each decision, keep it focused:

- what changed
- why it matters
- pros
- cons / risks
- alternatives
- my take
- key file references and short quotes only when useful

Pause after each decision and ask whether to continue. Do not output the complete review, all risks, all questions, and all final thoughts in one response unless the user explicitly asks for a "full report", "complete review", "dump everything", or "write it all at once".

If the user asks for a final summary after the walkthrough, then provide risks, questions for the author, and final recommendation.

## Output style

Write in a conversational, architect-to-architect tone. Start with the big picture in plain English, then go deeper into design decisions.

Use file references for important claims. Quote short code snippets only when they are strong evidence. Avoid large pasted diffs.

For normal walkthrough mode, do not use the full report template below. Use the pacing rules above.

For explicit full-report mode, prefer this structure:

```markdown
# PR #[number]: [title]

## Big-picture walkthrough
[Plain-English summary of what the PR is trying to accomplish and how it changes the system.]

## Main design decisions
### 1. [Decision name]
What changed: ...
Why this matters: ...
Evidence: `path/to/file.ext` [...short quote if useful...]
Pros:
- ...
Cons / risks:
- ...
Alternatives:
- ...
My take:
- ...

### 2. ...

## Architecture and integration impact
[How the change affects boundaries, data flow, ownership, provider coupling, runtime behavior, deployment, and future extensibility.]

## Rule and convention review
[Compare the PR against local repo rules first, then global rules, then existing code patterns. Call out meaningful alignment or violations.]

## Risks
- High: ...
- Medium: ...
- Low: ...

## Questions I would ask the author
- ...

## Final thoughts and insights
[Agent's own review: merge readiness, strongest parts, biggest concerns, what to verify before merge.]
```

Adapt section names naturally if the PR is small, but keep the same intent.

## Decision analysis pattern

For each major design decision, include:

- **What changed** — describe the implementation decision, not every line of code.
- **Why they likely did it** — infer the motivation from the PR and code.
- **Pros** — what this choice improves.
- **Cons / risks** — tradeoffs, complexity, hidden coupling, operational or security risks.
- **Alternatives** — realistic options the team could have chosen instead.
- **My take** — your recommendation or concern as the reviewing agent.

Alternatives should be practical. Do not invent theoretical rewrites that are out of scope unless the current approach has a serious flaw.

## Evidence guidelines

- Include file paths for claims about implementation decisions.
- Quote short snippets for important design evidence, security-sensitive logic, config shape, or API contracts.
- Use line references if available from the tooling; otherwise use file paths and function/class names.
- Do not flood the review with snippets. The user wants architectural signal, not pasted diff.

## Agent opinion

The review must include the agent's own insights. Do not only summarize the PR author's work.

Call out:

- Whether the design is directionally sound.
- Whether the change feels too coupled, too broad, under-tested, or operationally risky.
- What the PR author may have missed.
- What should be verified before merge.
- Whether you would approve, request changes, or ask clarifying questions.

## Risk rating

Include a risk section with practical ratings. Use this meaning:

- **High** — could cause security issues, auth bypass, data leakage, tenant isolation problems, production outage, or difficult rollback.
- **Medium** — could cause maintainability problems, provider coupling, subtle bugs, migration/deployment issues, or incomplete behavior.
- **Low** — minor gaps, small follow-ups, documentation/test improvements.

If there are no high risks, say that clearly.

## GitHub-only handling

Use GitHub PR tooling. Accept PR inputs like:

- `#37`
- `PR 37`
- Full GitHub PR URL
- Branch name only if it maps to an open GitHub PR via `gh pr list` or `gh pr view`.

If the PR number is missing or ambiguous, ask for it before proceeding.

Do not review unrelated local working tree changes as part of this skill unless the user explicitly says they are part of the PR context.

## Before finalizing

Before giving final thoughts or a final report, sanity-check that you covered:

- Big-picture purpose.
- Main design decisions.
- Pros and cons.
- Alternatives.
- Architecture/integration impact.
- Local and global rule alignment.
- File references and important quotes.
- Risks.
- Final thoughts and agent recommendation.

For interactive walkthroughs, this checklist is accumulated across the conversation. Do not force every item into the first response.
