---
name: video-creator
description: >-
  Generate short concept videos from a description. Breaks concepts into scenes,
  generates character references and first-frame images via Nano Banana Pro,
  then produces videos with Google Veo 3.1. Use when asked to create a short
  video, concept video, scene sequence, or animated clip.
metadata:
  {
    "ilia":
      {
        "emoji": "🎬",
        "requires": { "bins": ["uv"], "env": ["GEMINI_API_KEY"] },
        "primaryEnv": "GEMINI_API_KEY",
      },
  }
---

# Video Creator

Generate short concept videos by breaking a description into scenes, producing first-frame images, and rendering videos with Veo 3.1.

## When to Use

- User asks to create a short video, concept video, or animated sequence
- User provides a concept description and desired number of scenes
- User wants AI-generated video clips chained together into a coherent sequence

## Workflow

Follow these phases in order. Wait for user approval at each checkpoint before proceeding.

### Phase 0: Project Setup

1. Create a timestamped project directory in the current working directory:
   ```
   video-project-YYYYMMDD-HHMMSS/
     references/
     first-frames/
     videos/
   ```
2. Create `project.md` inside it with this template:

```markdown
# Video Project: [Concept Name]
Created: YYYY-MM-DD HH:MM:SS
Mode: (to be selected)
Aspect Ratio: 16:9

## Scenes

| # | Duration | Type | Visual Prompt | Audio Notes | First Frame | Video | Status |
|---|----------|------|---------------|-------------|-------------|-------|--------|

## References
```

Update `project.md` after each phase to track progress.

### Phase 1: Script & Scene Planning

1. Take the user's concept description and desired number of scenes.
2. Generate a scene-by-scene script. For each scene define:
   - **Scene number**
   - **Duration**: 4, 6, or 8 seconds
   - **Visual description**: detailed Veo prompt describing the scene
   - **Continuity type**: `fresh-start` (new setting/angle) or `continues-previous` (picks up where the last scene ended)
   - **Audio description**: what should be heard (dialogue, sound effects, ambient)
3. Present the full script to the user in a readable format.
4. **CHECKPOINT**: Wait for user approval before proceeding. Accept revisions.

### Phase 2: Character References & Scene 1 First Frame

1. Identify recurring characters, objects, or settings that need visual consistency.
2. For each, generate a reference image via Nano Banana Pro:
   ```bash
   uv run {skills.nano-banana-pro.baseDir}/scripts/generate_image.py \
     --prompt "Full body character reference sheet of [character description]. Clean white background, front-facing view, detailed and consistent design." \
     --filename "video-project-.../references/[character-name].png" \
     --resolution 1K
   ```
3. Designate the protagonist as the **main character reference**. This reference will be included in every first-frame generation to maintain visual consistency across the entire video.
4. Generate the first frame for Scene 1, using **all** character reference images that appear in the scene:
   ```bash
   uv run {skills.nano-banana-pro.baseDir}/scripts/generate_image.py \
     --prompt "[Scene 1 visual description as a single still frame, cinematic composition]" \
     --filename "video-project-.../first-frames/scene-01-first-frame.png" \
     -i "video-project-.../references/main-character.png" \
     -i "video-project-.../references/character-b.png" \
     --resolution 2K
   ```
   **IMPORTANT**: Always include the main character reference (`-i`) even if other character references are also included. Nano Banana Pro supports up to 14 input images — use as many as needed.
5. Update `project.md` with reference and first-frame paths.
6. **CHECKPOINT**: Present references and Scene 1 first frame to the user. Wait for approval.

### Phase 3: First Frames for All Fresh-Start Scenes

1. For every scene marked `fresh-start` (except Scene 1, already done), generate a first-frame image.
   **Always include the main character reference** plus any other character references that appear in the scene:
   ```bash
   uv run {skills.nano-banana-pro.baseDir}/scripts/generate_image.py \
     --prompt "[Scene N visual description as a single still frame, cinematic composition]" \
     --filename "video-project-.../first-frames/scene-NN-first-frame.png" \
     -i "video-project-.../references/main-character.png" \
     -i "video-project-.../references/character-b.png" \
     --resolution 2K
   ```
2. **Character consistency rule**: The main character reference must be passed as `-i` to every first-frame generation where that character appears, regardless of whether other references are also included. This is how Nano Banana Pro maintains the same face/appearance across scenes.
3. Update `project.md`.
4. **CHECKPOINT**: Present all first frames to the user. Wait for approval.

### Phase 4: Video Generation

1. Ask the user which Veo model to use:
   - `standard` — higher quality, slower (veo-3.1-generate-preview). Supports reference images and audio.
   - `fast` — faster generation (veo-3.1-fast-generate-preview). Does NOT support reference images, enhance-prompt, or audio.

2. **API constraints (from official Veo 3.1 docs)**:
   - `--image` (first-frame) and `--ref` (reference images) **CANNOT be combined** — use one or the other
   - Duration **MUST be 8s** when using: reference images, 1080p, or 4k resolution
   - `person_generation`: text-to-video uses `allow_all`, image-to-video and reference-to-video use `allow_adult`
   - Max 3 reference images via `--ref`
   - Videos are stored for 2 days — download immediately
   - All videos include SynthID watermarking

3. **Choose the right mode per scene**:

   **Option A: Image-to-video** (first-frame image, NO character refs):
   Best for: Scene 1 or scenes where the first frame has been generated with all characters baked in via Nano Banana Pro.
   ```bash
   uv run {baseDir}/scripts/generate_video.py \
     --prompt "[scene visual + audio description]" \
     --output "video-project-.../videos/scene-NN.mp4" \
     --model standard \
     --image "video-project-.../first-frames/scene-NN-first-frame.png" \
     --aspect-ratio 9:16 \
     --duration 6 \
     --person-generation allow_adult
   ```

   **Option B: Reference-to-video** (character refs, NO first-frame):
   Best for: Scenes where character consistency matters most. Duration is forced to 8s.
   The prompt must describe the full scene since there is no first-frame anchor.
   ```bash
   uv run {baseDir}/scripts/generate_video.py \
     --prompt "[detailed scene visual + audio description including setting, camera, lighting]" \
     --output "video-project-.../videos/scene-NN.mp4" \
     --model standard \
     --ref "video-project-.../references/main-character.png" \
     --ref "video-project-.../references/singer.png" \
     --ref "video-project-.../references/drummer.png" \
     --aspect-ratio 9:16 \
     --person-generation allow_adult
   ```
   Note: Duration auto-set to 8s. Up to 3 `--ref` images max.

   **Option C: Text-to-video** (prompt only, no images):
   ```bash
   uv run {baseDir}/scripts/generate_video.py \
     --prompt "[scene description]" \
     --output "video-project-.../videos/scene-NN.mp4" \
     --model standard \
     --aspect-ratio 9:16 \
     --duration 6 \
     --person-generation allow_all
   ```

4. **Recommended approach per scene type**:

   **For `continues-previous` scenes (MANDATORY steps)**:
   1. Extract the last frame from the previous scene using `extract_last_frame.py`
   2. Use **Option B (reference-to-video)** with `--ref` flags
   3. **Reference image selection — CRITICAL RULES**:

      **HARD LIMIT: Veo allows a maximum of 3 `--ref` images per generation.**

      **RULE: ALL characters visible in the scene MUST be represented in the refs.**
      **RULE: The last frame from the previous scene SHOULD be included for visual continuity.**

      Since both rules often require more than 3 slots, use this strategy:

      **When characters + last frame fit within 3 slots** (e.g., 1-2 characters + last frame):
      - Include ALL character refs + last frame. Simple.

      **When characters + last frame exceed 3 slots** (e.g., 3+ characters + last frame):
      - **The last frame already contains all existing characters visually** — so it doubles as both a continuity anchor AND a reference for characters already in the scene
      - Use slots as: (1) last frame, (2) main character ref, (3) new character appearing in this scene
      - The last frame covers existing characters (singer, drummer, etc.) since they're already visible in it
      - If there is NO new character (everyone is already established), use: (1) last frame, (2) main character ref, (3) most prominent supporting character ref

      **When there are 4+ characters and NO last frame** (e.g., fresh-start scene):
      - Use **Nano Banana Pro to generate a composite first frame** with all character refs baked into one image
      - Then use image-to-video mode with that composite as `--image`

   4. **Prompt requirements for continues-previous scenes**:
      - Describe the scene **continuing exactly from where the previous one ended**
      - Describe what ALL characters in the scene are doing, their positions, and the ongoing action
      - **Never repeat actions that already happened in a previous scene**
      - Be specific about physical actions (e.g., "taps the phone screen with his finger" not "uses the phone")

   Example for a continues-previous scene with 2 characters:
   ```bash
   uv run {baseDir}/scripts/extract_last_frame.py \
     --input "video-project-.../videos/scene-01.mp4" \
     --output "video-project-.../first-frames/scene-01-last-frame.png"

   uv run {baseDir}/scripts/generate_video.py \
     --prompt "[scene description continuing from previous]" \
     --output "video-project-.../videos/scene-02.mp4" \
     --model standard \
     --ref "video-project-.../first-frames/scene-01-last-frame.png" \
     --ref "video-project-.../references/main-character.png" \
     --ref "video-project-.../references/singer.png" \
     --aspect-ratio 9:16 \
     --person-generation allow_adult
   ```

   **For `fresh-start` scenes**:
   - Generate first frame via Nano Banana Pro with ALL character references baked in, then use **Option A** (image-to-video)
   - OR use **Option B** (reference-to-video) with character refs only (no last frame needed since it's a fresh start)

5. **Prompt best practices** (from Veo docs):
   - Include: subject, action, style, camera motion, composition, focus effects, ambiance
   - Camera: "aerial view", "eye-level", "dolly shot", "tracking shot"
   - Composition: "wide shot", "close-up", "medium shot"
   - Focus: "shallow focus", "deep focus", "soft focus"
   - For dialogue: use quotes for specific speech
   - For sound: explicitly describe sounds and ambient noise
   - Avoid negative phrasing ("no", "don't") — use descriptive terms instead

6. After each scene completes, update `project.md` and **show the result to the user**.
7. **CHECKPOINT after every scene**: Wait for user approval before proceeding to the next scene. If a scene looks wrong, offer to regenerate it.

### Phase 5: Review & Delivery

1. List all generated scene videos with their absolute paths.
2. Update `project.md` with final status for all scenes.
3. Automatically concatenate all scenes into the final video. Apply **crossfade transitions** between `fresh-start` scenes (scenes that cut to a new setting), and **direct concat** between `continues-previous` scenes:

   **Simple concat (all scenes flow continuously):**
   ```bash
   for f in video-project-.../videos/scene-*.mp4; do echo "file '$(pwd)/$f'"; done > video-project-.../filelist.txt
   ffmpeg -f concat -safe 0 -i video-project-.../filelist.txt -c copy video-project-.../final-output.mp4
   ```

   **With crossfade transitions between fresh-start scenes** (use when there are scene breaks):
   Build an ffmpeg filter_complex with `xfade` filters. For a 0.5s crossfade between scene N and N+1:
   ```bash
   # Example for 4 scenes where scene 3 is a fresh-start (needs transition):
   # Scenes 1→2: direct (continues-previous), 2→3: crossfade (fresh-start), 3→4: crossfade (fresh-start)
   ffmpeg \
     -i scene-01.mp4 -i scene-02.mp4 -i scene-03.mp4 -i scene-04.mp4 \
     -filter_complex "\
       [0:v][1:v]xfade=transition=fade:duration=0.5:offset=<scene1_dur - 0.5>[v01]; \
       [v01][2:v]xfade=transition=fade:duration=0.5:offset=<cumulative_dur - 0.5>[v012]; \
       [v012][3:v]xfade=transition=fade:duration=0.5:offset=<cumulative_dur - 0.5>[vout]; \
       [0:a][1:a]acrossfade=d=0.5[a01]; \
       [a01][2:a]acrossfade=d=0.5[a012]; \
       [a012][3:a]acrossfade=d=0.5[aout]" \
     -map "[vout]" -map "[aout]" video-project-.../final-output.mp4
   ```
   Adapt the offsets based on actual scene durations. Use `transition=fade` for clean cuts or `transition=wipeleft`, `transition=circleopen`, etc. for stylistic transitions.

4. Report the final video path to the user.

## Script Reference

### generate_video.py

```bash
uv run {baseDir}/scripts/generate_video.py \
  --prompt "description" \
  --output "output.mp4" \
  --model standard|fast \
  [--image "first-frame.png"] \
  [--ref "character-ref.png"] \
  [--aspect-ratio "16:9"|"9:16"] \
  [--duration 4|6|8] \
  [--resolution "720p"|"1080p"|"4k"] \
  [--generate-audio] \
  [--enhance-prompt] \
  [--person-generation allow_adult|allow_all|dont_allow] \
  [--poll-interval 10] \
  [--timeout 600] \
  [--api-key KEY]
```

### extract_last_frame.py

```bash
uv run {baseDir}/scripts/extract_last_frame.py \
  --input "video.mp4" \
  --output "last-frame.png"
```

## Notes

- The `fast` model does not support `--enhance-prompt` or `--generate-audio` flags. Always use `--no-enhance-prompt --no-audio` with the fast model.
- Video generation is async and can take 1-5 minutes per scene depending on model and duration.
- Generated videos are stored on Google's servers for 2 days before deletion — the script downloads them immediately.
- All outputs include SynthID watermarking.
- Default aspect ratio is 16:9. Use 9:16 for vertical/mobile-first videos.
- Veo supports durations of 4, 6, or 8 seconds per scene.
- Do not read generated images or videos back — report file paths only.
- Use timestamps in filenames: `yyyy-mm-dd-hh-mm-ss-name.ext`.
