---
name: remotion-promo-video
description: Build a polished Remotion promo video (Slack-style chats + product screenshots + typed text scenes + connector logos + synced typing SFX) with consistent branded background and clean pacing.
metadata:
  author: internal-assistant
  version: "1.0.0"
  homepage: https://www.remotion.dev/
  argument-hint: <repo-root>
  tags: remotion, promo-video, marketing, slack-chat, screenshots, typewriter, sfx, timeline
---

# remotion-promo-video

Create a **marketing-quality Remotion promo video** with:

- Clean, modern **white + black** aesthetic (startup vibe)
- A single **signature background** applied consistently across *all* scenes
- **Slack-like conversations** (2+ short scenarios tailored to your product)
- Inline **visual attachments** in chat (bar/pie/table) with tasteful colors
- **Real product screenshots** presented without zoom, labels, or gray overlays
- A **connectors scene** where logos pop in (from a connectors folder)
- Typed text screens with **per-letter typing SFX exactly synced** to character reveal
- Simple, deterministic timeline: no empty frames, no scene drift

This skill is designed to be reused across projects without re-explaining the same constraints.


## What this skill assumes

- You have a Remotion project (or a `promo-video/` folder) that contains:
  - `src/compositions/<MainComposition>.tsx` (timeline)
  - `src/components/` (scene components)
  - `src/theme.ts` (visual system)
  - `public/` (assets accessed via `staticFile()`)
- Your repo uses **Justfile recipes** for common workflows.

If your repo does not use `just`, translate the commands to your build system, but keep the same structure.


## Content intake (the agent should ask first)

This skill is intentionally **domain-agnostic**. Before generating or editing scenes, the agent should collect a minimal “content brief”.

If the user already provided all inputs, skip questions and proceed.

### Ask for these inputs

1) **Audience + goal**
  - Who is this for (engineers, leadership, customers)?
  - What outcome do we want (book a demo, install, sign in, try the product)?

2) **Two scenarios (or more)**
  - For each scenario:
    - user problem statement (1 sentence)
    - assistant value (1 sentence)
    - what the assistant should “do” (summarize, investigate, propose plan, generate artifacts)
    - any “attachments” to show (bar/pie/table) and what they represent

3) **Screenshots + order**
  - Which screenshots should appear (file paths), and in what order?
  - Any **banned** screenshots (never use)?
  - Any sensitive elements to blur/remove?

4) **Branding**
  - Logo files (e.g., `public/screenshots/brand-logo.svg`)
  - Background colors/accent palette (or permission to pick tasteful defaults)

5) **Connectors (optional)**
  - Should there be a connectors scene? If yes:
    - which logos (folder path)
    - any partner ordering constraints

6) **Copy constraints**
  - Any mandatory lines (e.g., “Powered by …”)
  - Claims to avoid (compliance/legal)
  - Words/tone to avoid

7) **Timing preferences**
  - Target duration (e.g., 45s / 60s)
  - Holds (chat end hold, text hold) if not default

### If inputs are missing

- The agent should propose a reasonable default (2 scenarios, 3–6 screenshots, connectors optional) and **ask the user to confirm**.
- Keep all scenario-specific content in data arrays/config so it’s easy to swap later.


## Core principle: define the “contract” first

To make the output repeatable, lock these decisions first and treat them like a contract.

### Visual contract

- **Canvas**: 1920×1080 @ 30fps
- **Typeface**: one font family (e.g., Inter)
- **Signature background**:
  - implemented once in `theme.backgroundImage`
  - applied once at the composition root (e.g., `<AbsoluteFill />`)
  - individual scenes must NOT override the global background
- **Surfaces** (cards, chat bubbles): white with soft border + soft shadow
- **No clutter**:
  - no screenshot captions/labels
  - no “duration badges”
  - no gray wash overlays on screenshots
- **Motion**:
  - small lift-in or fade-in is fine
  - avoid ken-burns / zoom unless explicitly required

### Timing contract

Use constants and compute durations from data:

- `FPS = 30`
- `XFADE` (crossfade overlap): 8–12 frames typical
- `TEXT_HOLD_SECONDS`: hold for text-only scenes (e.g., 1.0s)
- `CHAT_END_HOLD_SECONDS`: extra hold after last chat bubble (e.g., 1.5s)
- Screenshot scenes: fixed durations per slide, extend by +1s only when requested


## Quick start (repo workflow)

From repo root:

- Install dependencies:
  - `just video-install`
- Preview Remotion:
  - `just video-preview`
- Typecheck:
  - `just video-typecheck`
- Render:
  - `just video-render`


## Recommended project layout

Keep the following roles separated so you can swap content without changing the engine.

- `src/theme.ts`
  - global background
  - base colors
  - radii/shadows

- `src/Root.tsx`
  - registers compositions
  - uses a single exported `PROMO_DURATION_IN_FRAMES` from the timeline

- `src/compositions/<Main>.tsx`
  - timeline + durations
  - exports `PROMO_DURATION_IN_FRAMES`
  - defines and schedules scenes

- `src/components/`
  - `SlackConversation.tsx`, `SlackMessage.tsx` (chat)
  - `ChatVisual.tsx` (bar/pie/table attachments)
  - `TypedText.tsx` (typed segments + cursor + *per-letter SFX*)
  - `TypewriterScene.tsx` (typed explainer screen)
  - `ScreenshotShowcase.tsx` (blurred backdrop + sharp contain)
  - `ConnectorsScene.tsx` (logos pop-in)
  - `CallToActionCard.tsx` (outro)

- `public/`
  - `screenshots/` (copy screenshots here)
  - `connectors/` (copy connector logos here)
  - `sfx/` (generated WAV files)


## Asset ingestion rules (always do this)

### 1) Screenshots

- Copy screenshots into `public/screenshots/`.
- Always reference them via `staticFile("screenshots/<name>.png")`.
- Maintain an explicit ban list when needed.

**Ban list example**

If a project says “don’t use these”, remove all references from the timeline:

- `do-not-use-1.png`
- `do-not-use-2.png`
- `do-not-use-3.png`

### 2) Connector logos

- Copy logos into `public/connectors/`.
- Use fixed-size cards in a grid so they look consistent.


## Timeline rules (to avoid overlaps and empty frames)

### Scenes as blocks

Structure the timeline as a sequence of blocks:

1. Title (typed)
2. Scenario A chat
3. Scenario A screenshots
4. Explainer (typed)
5. Scenario B chat
6. Scenario B screenshots
7. Connectors (logos pop-in)
8. Outro/CTA (typed)

### Crossfades

For most transitions:

- `nextStart = prevStart + prevFrames - XFADE`

For the *final* transition into the CTA/outro (commonly requested):

- do **not** overlap; avoid “stacking” two final scenes
- `outroStart = connectorsStart + connectorsFrames`


## Chat: authoring conversations as data

Represent the conversation as an array of items:

- `message`
  - `fromFrame`, `from`, `name`, `text`
  - optional `chips` and `attachment`
- `typing`
  - assistant “thinking” indicator
  - `fromFrame`, `durationInFrames`

### End-of-chat hold must be computed

Do not guess chat duration.

Compute:

- `conversationEnd = max(lastMessage.fromFrame, lastTypingEndFrame)`
- `chatFrames = conversationEnd + CHAT_END_HOLD_SECONDS*FPS + XFADE`

This guarantees the last bubble is readable and you avoid drift when copy changes.

### Typing SFX timing rule

- Typing SFX should play when the **user is composing**.
- Do NOT play typing SFX during assistant “thinking” dots.


## Visual attachments in chat (bar/pie/table)

### Charts must be colored

Avoid monochrome charts.

Use a stable accent palette:

- blue `#2563eb`
- green `#16a34a`
- purple `#7c3aed`
- amber `#f59e0b`

### Tables must have subtle color accents

Recommended:

- tinted header background (very light)
- left accent stripe per row
- small colored dot in the first column per row

Keep it subtle; it should still read like enterprise UI.


## Screenshots: “clean product UI” presentation

The showcase should be:

- blurred backdrop to fill frame (low opacity)
- sharp screenshot layer on top with `objectFit: contain`
- no labels/captions
- no overlays/washes
- no ken-burns / no scaling if “don’t zoom” is required


## Typed text + EXACT per-letter typing SFX

### Typed text math (deterministic)

Reveal budget:

- `budget = floor(((frame - startFrame) / fps) * charsPerSecond)`

### Exact audio sync

Use a short `keystroke.wav` (~30–40ms) and schedule it per character at the first frame where that character becomes visible.

A character at index `i` becomes visible at:

- `appearLocal = ceil(((i + 1) * fps) / charsPerSecond)`
- `appearFrame = startFrame + appearLocal`

Rules:

- skip whitespace (spaces/newlines)
- keep volume low; many keystrokes can happen close together


## Production checklist (definition of done)

- [ ] Global background matches intro across all scenes
- [ ] No screenshot captions/labels anywhere
- [ ] No gray overlays/washes on screenshots
- [ ] No screenshot zoom/crop when requested
- [ ] Conversations have readable end hold (e.g., 1.5s)
- [ ] Text screens hold (e.g., 1.0s), except explicit exceptions
- [ ] No overlap between last two scenes (if requested)
- [ ] Charts + tables have distinct colors
- [ ] Typing SFX is per-letter and exactly synced on text screens
- [ ] Chat typing SFX starts on user composer typing, not assistant thinking
- [ ] `just video-typecheck` passes
- [ ] `just video-render` succeeds


## Troubleshooting

### “There is overlap between the last scenes”

- Remove the final `- XFADE` when computing the last scene start.

### “Typing sound is early/late”

- Ensure you are not using long looping WAVs.
- Use a `keystroke.wav` and schedule it by character appear frame.

### “Screenshots look zoomed in”

- Remove any `scale(>1)` on the blurred backdrop.
- Remove `clipPath: inset(...)` or any crop.
- Avoid any animated scaling.


## Notes for reuse across projects

To port this to a new project, you typically only change:

- screenshots in `public/screenshots/`
- connector logos in `public/connectors/`
- conversation item arrays (Scenario A / Scenario B / …)
- copy on Title / Explainer / Connectors / CTA
- (optionally) the 2–3 accent colors used by the global background
