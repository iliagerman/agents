#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-genai>=1.0.0",
# ]
# ///
"""
Generate videos using Google Veo 3.1 API.

Supports text-to-video and image-to-video (with a reference/first-frame image).

Usage:
    uv run generate_video.py --prompt "description" --output "scene.mp4" --model standard
    uv run generate_video.py --prompt "description" --output "scene.mp4" --model fast --image "first-frame.png"
"""

import argparse
import os
import sys
import time
from pathlib import Path


MODEL_MAP = {
    "standard": "veo-3.1-generate-preview",
    "fast": "veo-3.1-fast-generate-preview",
}


def get_api_key(provided_key: str | None) -> str | None:
    """Get API key from argument first, then environment."""
    if provided_key:
        return provided_key
    return os.environ.get("GEMINI_API_KEY")


def main():
    parser = argparse.ArgumentParser(
        description="Generate videos using Google Veo 3.1"
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Video description/prompt"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output video file path (e.g., scene-01.mp4)"
    )
    parser.add_argument(
        "--model", "-m",
        choices=["standard", "fast"],
        default="standard",
        help="Veo model: standard (higher quality) or fast (quicker generation)"
    )
    parser.add_argument(
        "--image", "-i",
        help="Reference/first-frame image path for image-to-video generation"
    )
    parser.add_argument(
        "--aspect-ratio",
        default="16:9",
        choices=["16:9", "9:16"],
        help="Video aspect ratio (default: 16:9)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=6,
        choices=[4, 6, 8],
        help="Video duration in seconds (default: 6)"
    )
    parser.add_argument(
        "--resolution",
        default="720p",
        choices=["720p", "1080p", "4k"],
        help="Video resolution (default: 720p)"
    )
    parser.add_argument(
        "--generate-audio",
        action="store_true",
        default=True,
        help="Generate audio with the video (default: True)"
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Disable audio generation"
    )
    parser.add_argument(
        "--enhance-prompt",
        action="store_true",
        default=True,
        help="Let Veo enhance the prompt (default: True)"
    )
    parser.add_argument(
        "--no-enhance-prompt",
        action="store_true",
        help="Disable prompt enhancement"
    )
    parser.add_argument(
        "--person-generation",
        default="allow_adult",
        choices=["allow_adult", "dont_allow"],
        help="Person generation policy (default: allow_adult)"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between status checks (default: 10)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum seconds to wait for generation (default: 600)"
    )
    parser.add_argument(
        "--api-key", "-k",
        help="Gemini API key (overrides GEMINI_API_KEY env var)"
    )

    args = parser.parse_args()

    # Resolve flags
    generate_audio = not args.no_audio
    enhance_prompt = not args.no_enhance_prompt

    # Get API key
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: No API key provided.", file=sys.stderr)
        print("Please either:", file=sys.stderr)
        print("  1. Provide --api-key argument", file=sys.stderr)
        print("  2. Set GEMINI_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    # Import after key check to avoid slow import on error
    from google import genai
    from google.genai import types


    # Initialise client
    client = genai.Client(api_key=api_key)

    # Set up output path
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve model
    model_id = MODEL_MAP[args.model]
    print(f"Model: {model_id}")
    print(f"Prompt: {args.prompt[:100]}{'...' if len(args.prompt) > 100 else ''}")

    # Load reference image if provided
    reference_image = None
    if args.image:
        try:
            reference_image = types.Image.from_file(location=args.image)
            print(f"Reference image: {args.image}")
        except Exception as e:
            print(f"Error loading reference image '{args.image}': {e}", file=sys.stderr)
            sys.exit(1)

    # Build config — only include params the model supports
    config_kwargs = dict(
        aspect_ratio=args.aspect_ratio,
        number_of_videos=1,
        duration_seconds=args.duration,
        person_generation=args.person_generation,
    )
    # enhance_prompt and generate_audio are not supported on all models
    if enhance_prompt:
        config_kwargs["enhance_prompt"] = True
    if generate_audio:
        config_kwargs["generate_audio"] = True

    try:
        config = types.GenerateVideosConfig(**config_kwargs)
    except TypeError as e:
        # Remove unsupported params and retry
        for param in ["enhance_prompt", "generate_audio"]:
            config_kwargs.pop(param, None)
        config = types.GenerateVideosConfig(**config_kwargs)

    print(f"Settings: {args.duration}s, {args.aspect_ratio}, {args.resolution}, audio={'on' if generate_audio else 'off'}")
    print(f"Generating video...")

    try:
        # Submit generation request
        kwargs = {
            "model": model_id,
            "prompt": args.prompt,
            "config": config,
        }
        if reference_image is not None:
            kwargs["image"] = reference_image

        operation = client.models.generate_videos(**kwargs)

        # Poll for completion
        start_time = time.time()
        while not operation.done:
            elapsed = int(time.time() - start_time)
            if elapsed > args.timeout:
                print(f"\nError: Timed out after {args.timeout}s. Try --timeout with a higher value or use --model fast.", file=sys.stderr)
                sys.exit(1)
            print(f"  Waiting... ({elapsed}s elapsed)", flush=True)
            time.sleep(args.poll_interval)
            operation = client.operations.get(operation)

        elapsed = int(time.time() - start_time)
        print(f"Generation completed in {elapsed}s")

        # Check for errors
        if operation.error:
            print(f"Error: Video generation failed: {operation.error}", file=sys.stderr)
            sys.exit(1)

        # Extract and save video
        result = operation.result
        if not result or not result.generated_videos:
            print("Error: No video was generated in the response.", file=sys.stderr)
            sys.exit(1)

        video = result.generated_videos[0]

        # The video may be accessible via a URI or inline data
        if hasattr(video, "video") and video.video:
            video_data = video.video
            if hasattr(video_data, "uri") and video_data.uri:
                # Download via authenticated request (URI requires API key)
                import urllib.request
                print(f"Downloading video from server...")
                separator = "&" if "?" in video_data.uri else "?"
                auth_url = f"{video_data.uri}{separator}key={api_key}"
                urllib.request.urlretrieve(auth_url, str(output_path))
            elif hasattr(video_data, "video_bytes") and video_data.video_bytes:
                output_path.write_bytes(video_data.video_bytes)
            else:
                print("Error: Video result has no accessible data (no URI or bytes).", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: Unexpected response format — no video data found.", file=sys.stderr)
            sys.exit(1)

        full_path = output_path.resolve()
        print(f"\nVideo saved: {full_path}")
        print(f"MEDIA: {full_path}")

    except Exception as e:
        print(f"Error generating video: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
