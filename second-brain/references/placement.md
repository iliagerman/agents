# Placement rules — where a new note goes

The goal: every note lands in the **most specific cluster whose subject clearly
contains it**, the tree stays shallow until depth is earned, and the agent **asks
the user instead of guessing** when it's genuinely unsure.

## The decision

After `tree` + `search "<topic>"`, descend from the root to the most specific
cluster whose subject fits, then choose one of:

### 1. Add to an existing cluster
Choose this when a cluster's subject **clearly contains** the note and no finer
sub-grouping is warranted yet.
- A one-off note with no recurring sub-topic goes **directly** into the nearest
  fitting cluster. Do **not** wrap it in a new single-note cluster.
- Example: a stray idea about your job → `work/` directly, not `work/ideas/one-idea/`.

### 2. Create a new sub-cluster
Choose this when the note opens a **distinct sub-subject that will plausibly gather
more notes**, or an existing cluster has grown heterogeneous and this note + its
siblings form a natural split.
- Signals: a new named thing with its own scope — a trip, a project, a client, a
  course, a year. (e.g. first note about a Ukraine trip → create
  `personal/travel/summer-2026-ukraine/`.)
- Signal: a cluster's `## Notes` list is long and clearly covers 2–3 sub-topics →
  split into sub-clusters.

### 3. Create a new top-level cluster
Only when the subject fits **no** existing top-level cluster. Top level is for broad
life domains (e.g. `work`, `personal`, `health`, `finance`). Add sparingly.

### 4. Ask the user (when ambiguous)
**Default to asking** rather than guessing whenever:
- Two or more clusters fit comparably well.
- It's unclear whether to reuse an existing cluster or create a new one.
- The subject is novel and could sit at multiple levels (top-level vs nested).
- The note spans subjects (could be `work` *or* `personal`).

Ask **one short question** that names the concrete candidate locations plus a "new
cluster" option, and let the user pick or redirect. Phrasing pattern:

> "This could go under **Personal → Travel → Summer 2026 Ukraine**, under **Work →
> Travel**, or I can start a **new cluster**. Which fits — or is it about something
> else?"

Or, when you just need to confirm the subject:

> "Is this related to your Ukraine trip, or is it a separate topic?"

Proceed only after the user answers. Then file per their choice.

## Principles

- **Shallow until earned.** Don't pre-build empty scaffolding. Depth should reflect
  real subject hierarchy, created when the second related note appears — or when the
  user signals a distinct subject.
- **Subjects, not single notes.** A cluster represents a subject expected to hold
  multiple notes. One note ≠ a cluster.
- **Reuse over proliferation.** `search` first; if a fitting note/cluster exists,
  extend it rather than making a near-duplicate.
- **Names:** cluster folder = kebab-case slug; human title lives in the index.
- **When you create or place, you maintain.** After any write, re-evaluate the
  affected `index.md` files up to the root and run `check` until clean (see
  `commands.md`).
