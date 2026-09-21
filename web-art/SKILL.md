---
name: web-art
description: >-
  Generate icons and images for web applications with transparent backgrounds.
  Analyzes app design language, generates via Gemini, removes background.
  Use when asked to create icons, illustrations, logos, or art for a webapp.
metadata:
  {
    "ilia":
      {
        "emoji": "🎨",
        "requires": { "bins": ["uv"], "env": ["GEMINI_API_KEY"] },
        "primaryEnv": "GEMINI_API_KEY",
      },
  }
---

# Web Art — Transparent Asset Generator

Generate icons, illustrations, and images for web applications that match the app's existing design language, delivered as transparent PNGs.

## When to Use

- User asks for an icon, logo, illustration, hero image, or any visual asset for their web app
- User wants images that match their app's existing style
- User needs transparent-background assets

## Workflow

Follow these phases in order. Do NOT skip Phase 1 — understanding the app's design is critical for producing cohesive assets.

### Phase 1: Analyze the App's Design Language

Before generating anything, examine the project to understand its visual identity:

1. **Search for design sources** — look for:
   - Tailwind config (`tailwind.config.*`) for color palette, border-radius, font families
   - CSS custom properties / design tokens (`:root` blocks, `variables.css`, `tokens.*`)
   - Theme files (e.g., `theme.ts`, `theme.js`, `_variables.scss`)
   - Existing image assets in `public/`, `assets/`, or `static/` directories
   - Component library usage (Material UI, Chakra, Radix, shadcn, etc.)

2. **Extract key attributes**:
   - **Color palette**: list all primary, secondary, accent, and background hex colors
   - **Style**: flat / material / skeuomorphic / glassmorphism / hand-drawn
   - **Shapes**: rounded (pill, large radius) vs sharp (square corners)
   - **Theme**: light / dark / both
   - **Typography feel**: modern sans-serif / corporate / playful / monospace-heavy

3. **Summarize** your findings in a short note before proceeding. This informs all later phases.

### Phase 2: Choose a Chroma-Key Background Color

Pick a solid background color for generation that will later be removed. The color MUST:

- **Not appear in the app's color palette** (from Phase 1)
- **Not be a natural color of the subject** (e.g., avoid green for plant/nature icons)

Priority order:
1. `#FF00FF` (magenta) — best default, rarely used in real designs
2. `#00FF00` (lime green) — avoid if subject involves nature/plants
3. `#0000FF` (pure blue) — avoid if app uses bright blue accents

Record the chosen hex color — you'll use it in Phases 3 and 4.

### Phase 3: Generate the Image via Nano Banana

Run the existing nano-banana-pro generation script:

```bash
uv run {skills.nano-banana-pro.baseDir}/scripts/generate_image.py \
  --prompt "<CRAFTED PROMPT>" \
  --filename "<TIMESTAMPED-PATH>.png" \
  --resolution 1K
```

**Prompt crafting rules** (follow these exactly):

1. **Start with**: `"The entire image canvas is filled edge-to-edge with a solid <COLOR NAME> (#XXXXXX) background. "`
2. **Describe the subject** using style cues from Phase 1:
   - Include art style (e.g., "flat design", "minimal line art", "3D rendered", "hand-drawn")
   - Reference color palette (e.g., "using shades of #3B82F6 and #1E293B")
   - Match the app's shape language (e.g., "with rounded corners", "geometric and angular")
   - **Prefer solid, filled shapes** — avoid hollow/outlined icons, cutout designs, or shapes with holes where the background would show through the interior of the subject
3. **For icon sets (multiple icons that must look consistent)**:
   - **Always use `--aspect-ratio 1:1`** to ensure square output
   - **Specify exact framing in EVERY prompt**: e.g., "The subject is centered in a square frame, occupying approximately 80% of the canvas, with equal padding on all sides"
   - **Use identical framing/composition language** across all prompts in the set — do NOT vary the layout instructions between icons
   - **Specify a consistent border style** if borders are desired (e.g., "with a golden ornamental square border frame") — use the SAME border description in every prompt
   - Example consistency block (copy verbatim into each icon prompt): `"The icon is centered in a square composition, filling approximately 80% of the canvas with equal margins on all four sides. The subject sits inside a [describe border] frame."`
4. **End with**: `"CRITICAL: The background must be a perfectly uniform solid <COLOR NAME> (#XXXXXX) color covering every pixel of the canvas from edge to edge. There must be no white borders, no margins, no secondary background colors, no frames, no borders, no outlines around the subject, no gradients, no shadows, no patterns, and no texture anywhere in the background. The <COLOR NAME> must extend to all four edges of the image."`
5. **Do NOT** mention transparency — the model cannot produce transparent images
6. **Filename**: use `yyyy-mm-dd-hh-mm-ss-<descriptive-name>.png` format

Example prompt:
```
The entire image canvas is filled edge-to-edge with a solid magenta (#FF00FF) background. A flat design gear/settings icon in steel blue (#64748B) and slate (#334155) with subtle depth, rounded edges, solid filled shape, modern minimalist style matching a dark-themed developer tool UI. CRITICAL: The background must be a perfectly uniform solid magenta (#FF00FF) color covering every pixel of the canvas from edge to edge. There must be no white borders, no margins, no secondary background colors, no frames, no borders, no outlines around the subject, no gradients, no shadows, no patterns, and no texture anywhere in the background. The magenta must extend to all four edges of the image.
```

### Phase 4: Remove the Background

Run the background removal script on the generated image:

```bash
uv run {baseDir}/scripts/remove_bg.py \
  --input "<path-from-phase-3>.png" \
  --output "<final-transparent-path>.png" \
  --bg-color "#XXXXXX" \
  --tolerance 30
```

- Use the same hex color from Phase 2 as `--bg-color`
- Default `--tolerance 30` works for most cases
- The script uses `--mode auto` by default, which runs a 4-step pipeline:
  1. **Edge flood fill** — BFS from image edges at base tolerance
  2. **Interior pockets** — removes bg-colored pixels not connected to edges (e.g., bg showing through holes/cutouts)
  3. **Boundary expansion** — grows mask into adjacent fringe pixels at `tolerance × --expansion` (default 3×) to catch degraded/washed-out bg variants
  4. **Hue cleanup** — BFS from mask boundary removing any pixel with the same hue as the bg color, regardless of RGB distance (catches pastel borders/frames Gemini sometimes draws)
  5. **Spill suppression** — neutralizes bg color tint from semi-transparent edge pixels so no color fringe bleeds through on any background
- Available modes:
  - `auto` (default) — full pipeline above. Best for most cases.
  - `edge` — only step 1 (edge flood fill). Use when the subject contains colors close to the bg color.
  - `global` — remove ALL pixels matching the bg color regardless of position. Most aggressive.
- Additional flags:
  - `--expansion 3.0` (default) — boundary expansion multiplier. Set to `1.0` to disable expansion.
  - `--feather 1` (default) — smooth edges; set to `0` for pixel-perfect sharp edges.
- **0% removal (nothing removed)**: The script auto-detects this and investigates. It samples edge pixels (filtering out white/black margins) to find the actual background color Gemini used, then retries with that color. This handles Gemini's tendency to drift from the requested chroma-key hex. No manual intervention needed in most cases. If auto-detection still fails, regenerate the image.
- If you see artifacts:
  - **Background remnants**: increase tolerance (try 40-50) or switch to `--mode global`
  - **Subject erosion**: decrease tolerance (try 15-25), switch to `--mode edge`, or lower `--expansion`
  - If neither helps, regenerate with a different background color

### Phase 5: Deliver the Result

- Report the final transparent PNG path to the user
- Do NOT read the image file back; just report the saved path
- Keep both the intermediate (with background) and final (transparent) files so the user can inspect either
- If the user is unsatisfied, offer to:
  - Re-generate with adjusted prompt wording
  - Try a different art style
  - Adjust tolerance/feather settings

## Troubleshooting

- **White bars / borders on sides of image**: Gemini sometimes generates the subject on a smaller canvas with white margins. If this happens, re-generate with stronger emphasis on edge-to-edge coverage. If the issue persists, you can pass a second `--bg-color` to the removal script (run it twice — once for the chroma-key color, once for `"#FFFFFF"` with low tolerance).
- **Background showing through cutouts/holes in the subject**: The default `--mode auto` handles this. If it still leaks, use `--mode global`.
- **Subject pixels being erased**: Lower the tolerance or switch to `--mode edge`.

## Notes

- Resolutions: `1K` (default, good for icons), `2K` (illustrations), `4K` (hero images)
- For icons, keep the subject centered with generous padding from edges
- Prefer solid, filled icon designs over outlined/hollow ones — open shapes expose the background through interior gaps, making clean removal harder
- For best background removal, avoid complex scenes with thin details at the edges (e.g., hair, wispy smoke) — bold clean shapes work best
- Both intermediate and final files are kept for inspection
