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
   - `standard` — higher quality, slower (veo-3.1-generate-preview)
   - `fast` — faster generation (veo-3.1-fast-generate-preview)

2. Process scenes **in sequential order**:

   **For `fresh-start` scenes** (have a first-frame image):
   ```bash
   uv run {baseDir}/scripts/generate_video.py \
     --prompt "[scene visual + audio description]" \
     --output "video-project-.../videos/scene-NN.mp4" \
     --model standard \
     --image "video-project-.../first-frames/scene-NN-first-frame.png" \
     --duration 6 \
     --generate-audio \
     --enhance-prompt
   ```

   **For `continues-previous` scenes**:
   First, extract the last frame from the preceding scene:
   ```bash
   uv run {baseDir}/scripts/extract_last_frame.py \
     --input "video-project-.../videos/scene-(NN-1).mp4" \
     --output "video-project-.../first-frames/scene-NN-last-frame-raw.png"
   ```
   Then regenerate the first frame through Nano Banana Pro, using the extracted last frame **plus all character references** to enforce consistency. This prevents character drift across scenes:
   ```bash
   uv run {skills.nano-banana-pro.baseDir}/scripts/generate_image.py \
     --prompt "[Scene N visual description as a single still frame, continuing from previous scene]" \
     --filename "video-project-.../first-frames/scene-NN-first-frame.png" \
     -i "video-project-.../first-frames/scene-NN-last-frame-raw.png" \
     -i "video-project-.../references/main-character.png" \
     -i "video-project-.../references/character-b.png" \
     --resolution 2K
   ```
   Then generate the video using the regenerated first frame:
   ```bash
   uv run {baseDir}/scripts/generate_video.py \
     --prompt "[scene visual + audio description, continuing from previous scene]" \
     --output "video-project-.../videos/scene-NN.mp4" \
     --model standard \
     --image "video-project-.../first-frames/scene-NN-first-frame.png" \
     --duration 6 \
     --generate-audio \
     --enhance-prompt
   ```

3. After each scene completes, update `project.md` and report progress.
4. If a scene looks wrong, offer to regenerate it before moving on.

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
  [--aspect-ratio "16:9"|"9:16"] \
  [--duration 4|6|8] \
  [--resolution "720p"|"1080p"|"4k"] \
  [--generate-audio] \
  [--enhance-prompt] \
  [--person-generation allow_adult|dont_allow] \
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
