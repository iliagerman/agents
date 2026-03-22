#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "opencv-python-headless>=4.8.0",
# ]
# ///
"""
Extract the last frame from a video file and save it as a PNG image.

Used to chain scenes together: the last frame of one scene becomes the
reference/first-frame image for the next scene's video generation.

Usage:
    uv run extract_last_frame.py --input "scene-01.mp4" --output "scene-02-ref.png"
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Extract the last frame from a video as a PNG"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input video file path"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output PNG file path"
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Import after arg check
    import cv2

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        print(f"Error: Could not open video: {input_path}", file=sys.stderr)
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        print(f"Error: Video has no frames: {input_path}", file=sys.stderr)
        cap.release()
        sys.exit(1)

    # Seek to last frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print(f"Error: Could not read last frame from: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Save as PNG (cv2 writes in BGR, which is fine for cv2.imwrite)
    cv2.imwrite(str(output_path), frame)

    full_path = output_path.resolve()
    print(f"Last frame extracted (frame {total_frames - 1} of {total_frames})")
    print(f"Saved: {full_path}")
    print(f"MEDIA: {full_path}")


if __name__ == "__main__":
    main()
