---
name: external-video-slideshow
description: Composing external videos with animated text slides for social media (TikTok, Instagram Reels, Facebook). Safe zones, typing animation, two-color text, optional ElevenLabs narration.
metadata:
  tags: video, slideshow, social, tiktok, instagram, facebook, safe-zone, typing, narration, elevenlabs
---

# External video slideshow with text slides

Use this rule when the user provides external video files (e.g. `video1.mp4` … `video4.mp4`) and wants animated text cards inserted between them — optimized for vertical social platforms.

## Composition dimensions

Always use **1080×1920** (9:16) for TikTok / Instagram Reels / Facebook Reels unless the user specifies otherwise.

```tsx
import { Composition } from "remotion";

<Composition
  id="Slideshow"
  component={Slideshow}
  width={1080}
  height={1920}
  fps={30}
  durationInFrames={totalFrames}
/>;
```

## Safe zone

Social platforms overlay UI elements (username, caption, buttons) on top and bottom. Keep all text inside the **safe zone**:

- **Top inset**: 15% of height (288px at 1920h)
- **Bottom inset**: 20% of height (384px at 1920h)
- **Left/Right inset**: 5% of width (54px at 1080w)

```tsx
const SAFE_ZONE: React.CSSProperties = {
  position: "absolute",
  top: "15%",
  bottom: "20%",
  left: "5%",
  right: "5%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
```

Always wrap text content in a safe-zone container. Videos can be full-bleed.

## Two-color text styling

Use two contrasting colors to make text pop — a primary color for the main words and an accent/highlight color for key words.

```tsx
const COLOR_PRIMARY = "#FFFFFF";
const COLOR_ACCENT = "#FFD700"; // or any vibrant accent

// Wrap key words in a span with the accent color
const TwoColorText: React.FC<{ text: string; accentWords: string[] }> = ({
  text,
  accentWords,
}) => {
  const words = text.split(" ");
  return (
    <div
      style={{
        fontSize: 64,
        fontWeight: 800,
        lineHeight: 1.3,
        textAlign: "center",
        textShadow: "0 4px 12px rgba(0,0,0,0.7)",
      }}
    >
      {words.map((word, i) => {
        const isAccent = accentWords.some(
          (a) => word.toLowerCase().replace(/[^a-z]/g, "") === a.toLowerCase()
        );
        return (
          <span
            key={i}
            style={{ color: isAccent ? COLOR_ACCENT : COLOR_PRIMARY }}
          >
            {word}{" "}
          </span>
        );
      })}
    </div>
  );
};
```

## Typing animation for text slides

Use string slicing (never per-character opacity). See also [text-animations.md](text-animations.md).

```tsx
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

const TypingText: React.FC<{
  text: string;
  accentWords: string[];
  charsPerFrame?: number;
}> = ({ text, accentWords, charsPerFrame = 0.5 }) => {
  const frame = useCurrentFrame();
  const visibleChars = Math.floor(frame * charsPerFrame);
  const displayed = text.slice(0, visibleChars);

  return (
    <div style={SAFE_ZONE}>
      <TwoColorText text={displayed} accentWords={accentWords} />
    </div>
  );
};
```

## Sequencing videos and text slides

Use `<Series>` to place videos and text cards back-to-back. Premount text sequences for smooth transitions.

```tsx
import { Series, staticFile } from "remotion";
import { Video } from "@remotion/media";

const { fps } = useVideoConfig();

<Series>
  {/* Video 1 */}
  <Series.Sequence durationInFrames={video1Duration}>
    <Video src={staticFile("video1.mp4")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  </Series.Sequence>

  {/* Text slide between video 1 and 2 */}
  <Series.Sequence durationInFrames={3 * fps} premountFor={fps}>
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <TypingText text="Your text here" accentWords={["text"]} />
    </AbsoluteFill>
  </Series.Sequence>

  {/* Video 2 */}
  <Series.Sequence durationInFrames={video2Duration}>
    <Video src={staticFile("video2.mp4")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  </Series.Sequence>

  {/* ... repeat pattern ... */}
</Series>;
```

### Making videos fill 9:16

External videos may not be 9:16. Always use `objectFit: "cover"` to fill the frame and avoid black bars:

```tsx
<Video
  src={staticFile("video1.mp4")}
  style={{
    width: "100%",
    height: "100%",
    objectFit: "cover",
  }}
/>
```

## Optional: ElevenLabs narration

When the user requests narration for the text slides, use the **elevenlabs skill** to generate speech audio for each text card. Then layer the audio with the text slide.

### Workflow

1. Use the `elevenlabs` skill to generate an MP3 for each text string.
2. Place the generated audio files in `public/` (e.g. `public/narration-1.mp3`).
3. Use `getAudioDurationInSeconds()` from `@remotion/media` to get the audio duration and size the text slide to match.
4. Layer the `<Audio>` component with the text slide:

```tsx
import { Audio } from "@remotion/media";
import { staticFile } from "remotion";

<Series.Sequence durationInFrames={narration1DurationFrames} premountFor={fps}>
  <AbsoluteFill style={{ backgroundColor: "#000" }}>
    <TypingText text="Your narrated text" accentWords={["narrated"]} />
    <Audio src={staticFile("narration-1.mp3")} />
  </AbsoluteFill>
</Series.Sequence>;
```

### Sizing text slides to narration length

```tsx
import { getAudioDurationInSeconds } from "@remotion/media/audio-duration";

// In calculateMetadata or a setup script:
const narrationSec = await getAudioDurationInSeconds("public/narration-1.mp3");
const narrationFrames = Math.ceil(narrationSec * fps);
```

Adjust the typing speed (`charsPerFrame`) so the typing animation finishes just before the audio ends:

```tsx
const charsPerFrame = text.length / (narrationFrames - holdFrames);
```

Where `holdFrames` is a small buffer (e.g. `0.5 * fps`) to let the full text sit on screen before transitioning.

## Checklist

- [ ] Composition is 1080×1920 at 30fps
- [ ] All text is inside the safe zone (top 15%, bottom 20%, sides 5%)
- [ ] Text uses two colors (primary + accent on key words)
- [ ] Text appears with typing animation (string slicing, not opacity)
- [ ] Videos use `objectFit: "cover"` for full-bleed
- [ ] If narration requested: use elevenlabs skill, match slide duration to audio length
- [ ] Premount text sequences for smooth transitions
