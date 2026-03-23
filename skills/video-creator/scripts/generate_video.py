#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-genai>=1.0.0",
# ]
# ///
"""
Generate videos using Google Veo 3.1 SDK.

Modes:
- Text-to-video: prompt only (person_generation=allow_all)
- Image-to-video: prompt + --image (person_generation=allow_adult)
- Reference-to-video: prompt + --ref (up to 3, duration forced to 8s, person_generation=allow_adult)

Note: --image and --ref cannot be combined (API limitation).
Duration must be 8 when using reference images, 1080p, or 4k resolution.

Usage:
    uv run generate_video.py --prompt "description" --output "scene.mp4"
    uv run generate_video.py --prompt "description" --output "scene.mp4" --image "first-frame.png"
    uv run generate_video.py --prompt "description" --output "scene.mp4" --ref "char1.png" --ref "char2.png"
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


def main():
    parser = argparse.ArgumentParser(description="Generate videos using Google Veo 3.1")
    parser.add_argument("--prompt", "-p", required=True, help="Video description/prompt")
    parser.add_argument("--output", "-o", required=True, help="Output video file path")
    parser.add_argument("--model", "-m", choices=["standard", "fast"], default="standard")
    parser.add_argument("--image", "-i", help="First-frame image path (image-to-video mode)")
    parser.add_argument("--ref", action="append", dest="references",
                        help="Reference image path for character/asset consistency (up to 3)")
    parser.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "9:16"])
    parser.add_argument("--duration", type=int, default=6, choices=[4, 6, 8])
    parser.add_argument("--resolution", default="720p", choices=["720p", "1080p", "4k"])
    parser.add_argument("--generate-audio", action="store_true", default=False)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--enhance-prompt", action="store_true", default=False)
    parser.add_argument("--no-enhance-prompt", action="store_true")
    parser.add_argument("--person-generation", default=None,
                        choices=["allow_adult", "allow_all", "dont_allow"])
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--api-key", "-k", help="Gemini API key")

    args = parser.parse_args()

    refs = args.references or []

    # Validate: can't combine --image and --ref
    if args.image and refs:
        print("Error: Cannot combine --image (first-frame) with --ref (reference images). "
              "Use one or the other.", file=sys.stderr)
        sys.exit(1)

    if len(refs) > 3:
        print("Error: Maximum 3 reference images allowed.", file=sys.stderr)
        sys.exit(1)

    # Auto-set duration to 8 when using reference images, 1080p, or 4k
    if refs and args.duration != 8:
        print(f"Note: Duration forced to 8s (required for reference images).")
        args.duration = 8
    if args.resolution in ("1080p", "4k") and args.duration != 8:
        print(f"Note: Duration forced to 8s (required for {args.resolution}).")
        args.duration = 8

    # Auto-set person_generation based on mode
    if args.person_generation is None:
        if args.image or refs:
            args.person_generation = "allow_adult"
        else:
            args.person_generation = "allow_all"

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: No API key. Use --api-key or set GEMINI_API_KEY.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model_id = MODEL_MAP[args.model]

    # Determine mode
    if refs:
        mode = "reference-to-video"
    elif args.image:
        mode = "image-to-video"
    else:
        mode = "text-to-video"

    print(f"Model: {model_id}")
    print(f"Mode: {mode}")
    print(f"Prompt: {args.prompt[:100]}{'...' if len(args.prompt) > 100 else ''}")
    if args.image:
        print(f"First-frame: {args.image}")
    for r in refs:
        print(f"Reference: {r}")
    print(f"Settings: {args.duration}s, {args.aspect_ratio}, {args.resolution}, "
          f"person={args.person_generation}, "
          f"audio={'on' if args.generate_audio else 'off'}, "
          f"enhance={'on' if args.enhance_prompt else 'off'}")
    print(f"Generating video...")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Build config
        config_kwargs = dict(
            aspect_ratio=args.aspect_ratio,
            number_of_videos=1,
            duration_seconds=args.duration,
            person_generation=args.person_generation,
        )

        # Add optional params
        if args.enhance_prompt:
            config_kwargs["enhance_prompt"] = True
        if args.generate_audio and not args.no_audio:
            config_kwargs["generate_audio"] = True

        # Add reference images to config
        if refs:
            reference_images = []
            for rp in refs:
                ref_img = types.Image.from_file(location=rp)
                reference_images.append(
                    types.VideoGenerationReferenceImage(
                        image=ref_img,
                        reference_type="asset",
                    )
                )
            config_kwargs["reference_images"] = reference_images

        config = types.GenerateVideosConfig(**config_kwargs)

        # Build generation kwargs
        gen_kwargs = {
            "model": model_id,
            "prompt": args.prompt,
            "config": config,
        }

        # Add first-frame image (only for image-to-video mode)
        if args.image:
            gen_kwargs["image"] = types.Image.from_file(location=args.image)

        # Generate
        operation = client.models.generate_videos(**gen_kwargs)

        # Poll for completion
        start_time = time.time()
        while not operation.done:
            elapsed = int(time.time() - start_time)
            if elapsed > args.timeout:
                raise Exception(f"Timed out after {args.timeout}s")
            print(f"  Waiting... ({elapsed}s elapsed)", flush=True)
            time.sleep(args.poll_interval)
            operation = client.operations.get(operation)

        elapsed = int(time.time() - start_time)
        print(f"Generation completed in {elapsed}s")

        if operation.error:
            raise Exception(f"Generation failed: {operation.error}")

        # Save video using official SDK pattern
        video = operation.response.generated_videos[0]
        print("Downloading video from server...")
        client.files.download(file=video.video)
        video.video.save(str(output_path))

        full_path = output_path.resolve()
        print(f"\nVideo saved: {full_path}")
        print(f"MEDIA: {full_path}")

    except Exception as e:
        print(f"Error generating video: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
