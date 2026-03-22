#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pillow>=10.0.0",
#     "numpy>=1.24.0",
# ]
# ///
"""
Remove a known solid-color background from an image, producing a transparent PNG.

In 'auto' mode (default), runs a multi-step pipeline:
  1. Edge flood fill at base tolerance
  2. Interior pocket removal (bg pixels not connected to edges)
  3. Boundary expansion at tolerance * --expansion (catches degraded fringe)
  4. Hue-based cleanup (catches pastel/washed-out bg variants and decorative borders)
  5. Spill suppression (neutralizes bg color tint from semi-transparent edge pixels)

Usage:
    uv run remove_bg.py --input in.png --output out.png --bg-color "#FF00FF"
    uv run remove_bg.py --input in.png --output out.png --bg-color "#FF00FF" --tolerance 40 --feather 2
    uv run remove_bg.py --input in.png --output out.png --bg-color "#FF00FF" --mode global
"""

import argparse
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    """Parse a hex color string like '#FF00FF' to an (R, G, B) tuple."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        raise ValueError(f"Invalid hex color: #{hex_str}")
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


def color_distance(pixel_rgb: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Euclidean distance between pixel RGB values and a target color."""
    return np.sqrt(np.sum((pixel_rgb.astype(np.float64) - target.astype(np.float64)) ** 2, axis=-1))


def flood_fill_edges(dist: np.ndarray, tolerance: float) -> np.ndarray:
    """
    BFS flood fill from all edge pixels whose color distance is within tolerance.
    Returns a boolean mask where True = background pixel.
    """
    h, w = dist.shape
    mask = np.zeros((h, w), dtype=bool)
    queue = deque()

    # Seed from all four edges
    for x in range(w):
        for y in (0, h - 1):
            if not mask[y, x] and dist[y, x] <= tolerance:
                mask[y, x] = True
                queue.append((y, x))
    for y in range(1, h - 1):
        for x in (0, w - 1):
            if not mask[y, x] and dist[y, x] <= tolerance:
                mask[y, x] = True
                queue.append((y, x))

    # BFS
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and dist[ny, nx] <= tolerance:
                mask[ny, nx] = True
                queue.append((ny, nx))

    return mask


def expand_mask_boundary(mask: np.ndarray, dist: np.ndarray, expanded_tolerance: float) -> np.ndarray:
    """
    Grow the mask into adjacent pixels that match within expanded_tolerance.
    This catches fringe pixels that are slightly off from the bg color.
    """
    h, w = mask.shape
    queue = deque()

    # Find current boundary pixels (mask pixels adjacent to non-mask)
    for cy in range(h):
        for cx in range(w):
            if mask[cy, cx]:
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx]:
                        if dist[ny, nx] <= expanded_tolerance:
                            mask[ny, nx] = True
                            queue.append((ny, nx))

    # Continue BFS at expanded tolerance
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and dist[ny, nx] <= expanded_tolerance:
                mask[ny, nx] = True
                queue.append((ny, nx))

    return mask


def hue_cleanup(pixels: np.ndarray, mask: np.ndarray, bg_color: tuple[int, int, int],
                 hue_tolerance: float = 30.0, min_saturation: float = 0.2) -> np.ndarray:
    """
    Remove remaining pixels that share the same hue as the background color,
    even if their RGB euclidean distance is high (e.g., pastel/washed-out variants).
    Only removes pixels adjacent to the existing mask (connected to background via BFS).

    Args:
        hue_tolerance: max circular hue difference in degrees (0-360 hue wheel, max distance 180).
        min_saturation: minimum HSV saturation (0-1) to consider — very desaturated pixels are skipped.
    """
    h, w = mask.shape
    rgb = pixels[:, :, :3].astype(np.float64)

    # Compute bg hue in degrees (0-360)
    bg_r, bg_g, bg_b = bg_color[0] / 255.0, bg_color[1] / 255.0, bg_color[2] / 255.0
    bg_max = max(bg_r, bg_g, bg_b)
    bg_min = min(bg_r, bg_g, bg_b)
    bg_delta = bg_max - bg_min
    if bg_delta < 0.01:
        return mask  # bg is achromatic, hue cleanup not applicable
    if bg_max == bg_r:
        bg_hue = 60 * (((bg_g - bg_b) / bg_delta) % 6)
    elif bg_max == bg_g:
        bg_hue = 60 * (((bg_b - bg_r) / bg_delta) + 2)
    else:
        bg_hue = 60 * (((bg_r - bg_g) / bg_delta) + 4)

    # Vectorized HSV computation for all non-masked pixels
    candidates = ~mask
    if not candidates.any():
        return mask

    cand_rgb = rgb[candidates] / 255.0
    c_max = cand_rgb.max(axis=1)
    c_min = cand_rgb.min(axis=1)
    delta = c_max - c_min

    # Saturation
    sat = np.where(c_max > 0, delta / c_max, 0)

    # Hue
    hue = np.zeros(len(delta))
    r, g, b = cand_rgb[:, 0], cand_rgb[:, 1], cand_rgb[:, 2]
    red_mask = (c_max == r) & (delta > 0.01)
    green_mask = (c_max == g) & (delta > 0.01) & ~red_mask
    blue_mask = (c_max == b) & (delta > 0.01) & ~red_mask & ~green_mask
    hue[red_mask] = 60 * (((g[red_mask] - b[red_mask]) / delta[red_mask]) % 6)
    hue[green_mask] = 60 * (((b[green_mask] - r[green_mask]) / delta[green_mask]) + 2)
    hue[blue_mask] = 60 * (((r[blue_mask] - g[blue_mask]) / delta[blue_mask]) + 4)

    # Hue distance (circular)
    hue_diff = np.abs(hue - bg_hue)
    hue_diff = np.minimum(hue_diff, 360 - hue_diff)

    # Pixels matching bg hue with sufficient saturation
    hue_match = (hue_diff <= hue_tolerance) & (sat >= min_saturation)

    if not hue_match.any():
        return mask

    # Build a full-size hue match map
    hue_match_full = np.zeros((h, w), dtype=bool)
    hue_match_full[candidates] = hue_match

    # Only remove hue-matched pixels that are adjacent to existing mask (BFS)
    queue = deque()
    for cy in range(h):
        for cx in range(w):
            if mask[cy, cx]:
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and hue_match_full[ny, nx] and not mask[ny, nx]:
                        mask[ny, nx] = True
                        queue.append((ny, nx))

    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and hue_match_full[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                queue.append((ny, nx))

    return mask


def suppress_spill(pixels: np.ndarray, alpha: np.ndarray, bg_color: tuple[int, int, int]) -> np.ndarray:
    """
    Neutralize background color spill from semi-transparent boundary pixels.
    For any pixel with partial alpha, remove the bg color contribution from its RGB
    so that when composited onto any background, no color fringe is visible.
    """
    semi = (alpha > 0) & (alpha < 255)
    if not semi.any():
        return pixels

    bg = np.array(bg_color, dtype=np.float64)
    result = pixels.copy()

    # For semi-transparent pixels, estimate the foreground color by
    # removing the bg contribution: fg = (pixel - bg * (1-a)) / a
    a = alpha[semi].astype(np.float64) / 255.0
    px = result[semi][:, :3].astype(np.float64)

    # Estimate foreground contribution
    fg = (px - bg * (1.0 - a[:, None])) / np.maximum(a[:, None], 0.01)
    fg = np.clip(fg, 0, 255).astype(np.uint8)

    result[semi, 0] = fg[:, 0]
    result[semi, 1] = fg[:, 1]
    result[semi, 2] = fg[:, 2]

    return result


def feather_alpha(alpha: np.ndarray, radius: int) -> np.ndarray:
    """Apply a slight blur to the alpha channel boundary for smoother edges."""
    if radius <= 0:
        return alpha
    alpha_img = Image.fromarray(alpha, mode="L")
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.array(alpha_img)


def detect_actual_bg_color(pixels: np.ndarray, expected_bg: tuple[int, int, int]) -> tuple[int, int, int] | None:
    """
    Sample edge pixels (not just corners) to find the actual dominant background color.

    Gemini sometimes generates backgrounds that drift from the requested chroma-key color.
    This function samples pixels along all four edges, filters out white/near-white pixels
    (since Gemini sometimes adds white margins), and finds the most common color cluster
    that is hue-similar to the expected background.

    Returns the detected color if it differs from expected_bg, or None if no better match found.
    """
    h, w = pixels.shape[:2]
    rgb = pixels[:, :, :3]

    # Sample every 4th pixel along all four edges (avoid corners which are often white)
    edge_pixels = []
    margin = max(1, min(w, h) // 20)  # skip a small margin inward from corners
    # Top and bottom edges
    for x in range(margin, w - margin, 4):
        edge_pixels.append(rgb[0, x])
        edge_pixels.append(rgb[h - 1, x])
    # Left and right edges
    for y in range(margin, h - margin, 4):
        edge_pixels.append(rgb[y, 0])
        edge_pixels.append(rgb[y, w - 1])

    if not edge_pixels:
        return None

    edge_arr = np.array(edge_pixels, dtype=np.float64)

    # Filter out white/near-white pixels (distance < 60 from pure white)
    white = np.array([255.0, 255.0, 255.0])
    white_dist = np.sqrt(np.sum((edge_arr - white) ** 2, axis=1))
    non_white = edge_arr[white_dist >= 60]

    # Also filter out black/near-black pixels
    black = np.array([0.0, 0.0, 0.0])
    black_dist = np.sqrt(np.sum((non_white - black) ** 2, axis=1))
    candidates = non_white[black_dist >= 60]

    if len(candidates) < 10:
        return None

    # Compute hue of expected bg
    bg_r, bg_g, bg_b = expected_bg[0] / 255.0, expected_bg[1] / 255.0, expected_bg[2] / 255.0
    bg_max, bg_min = max(bg_r, bg_g, bg_b), min(bg_r, bg_g, bg_b)
    bg_delta = bg_max - bg_min
    if bg_delta < 0.01:
        return None  # achromatic bg, can't match by hue
    if bg_max == bg_r:
        bg_hue = 60 * (((bg_g - bg_b) / bg_delta) % 6)
    elif bg_max == bg_g:
        bg_hue = 60 * (((bg_b - bg_r) / bg_delta) + 2)
    else:
        bg_hue = 60 * (((bg_r - bg_g) / bg_delta) + 4)

    # Filter candidates by hue similarity to expected bg (within 45 degrees)
    cand_norm = candidates / 255.0
    c_max = cand_norm.max(axis=1)
    c_min = cand_norm.min(axis=1)
    delta = c_max - c_min
    chromatic = delta > 0.05

    if not chromatic.any():
        return None

    cand_chromatic = candidates[chromatic]
    cn = cand_norm[chromatic]
    d = delta[chromatic]
    r, g, b = cn[:, 0], cn[:, 1], cn[:, 2]
    cm = c_max[chromatic]

    hue = np.zeros(len(d))
    rm = cm == r
    gm = (cm == g) & ~rm
    bm = ~rm & ~gm
    hue[rm] = 60 * (((g[rm] - b[rm]) / d[rm]) % 6)
    hue[gm] = 60 * (((b[gm] - r[gm]) / d[gm]) + 2)
    hue[bm] = 60 * (((r[bm] - g[bm]) / d[bm]) + 4)

    hue_diff = np.abs(hue - bg_hue)
    hue_diff = np.minimum(hue_diff, 360 - hue_diff)
    hue_match = hue_diff <= 45

    if not hue_match.any():
        return None

    matched = cand_chromatic[hue_match]

    # Return the median color of matched edge pixels (robust to outliers)
    median_color = np.median(matched, axis=0).astype(int)
    detected = (int(median_color[0]), int(median_color[1]), int(median_color[2]))

    # Only return if it's meaningfully different from expected
    dist_from_expected = np.sqrt(sum((a - b) ** 2 for a, b in zip(detected, expected_bg)))
    if dist_from_expected < 10:
        return None  # close enough, no correction needed

    return detected


def main():
    parser = argparse.ArgumentParser(
        description="Remove a solid-color background from an image to produce a transparent PNG."
    )
    parser.add_argument("--input", "-i", required=True, help="Input image path")
    parser.add_argument("--output", "-o", required=True, help="Output transparent PNG path")
    parser.add_argument(
        "--bg-color", "-c", required=True,
        help="Background color to remove as hex (e.g. '#FF00FF')"
    )
    parser.add_argument(
        "--tolerance", "-t", type=float, default=30.0,
        help="Color distance tolerance for flood fill (default: 30)"
    )
    parser.add_argument(
        "--feather", "-f", type=int, default=1,
        help="Alpha feather radius in pixels for smooth edges (default: 1, 0 to disable)"
    )
    parser.add_argument(
        "--mode", "-m", choices=["auto", "edge", "global"], default="auto",
        help=(
            "Background detection mode (default: auto). "
            "'edge' = flood fill from edges only (conservative). "
            "'global' = remove ALL pixels matching bg color (aggressive). "
            "'auto' = edge flood fill + interior pockets + boundary expansion + spill suppression."
        ),
    )
    parser.add_argument(
        "--expansion", "-e", type=float, default=3.0,
        help=(
            "Boundary expansion multiplier for catching fringe pixels (default: 3.0). "
            "The mask is grown into adjacent pixels within tolerance * this multiplier. "
            "Set to 1.0 to disable boundary expansion. Only used in auto mode."
        ),
    )
    args = parser.parse_args()

    # Parse background color
    try:
        bg_color = parse_hex_color(args.bg_color)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Load image
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    img = Image.open(input_path).convert("RGBA")
    pixels = np.array(img)
    print(f"Loaded image: {input_path} ({img.width}x{img.height})")

    # Pre-compute color distances
    print(f"Removing background color {args.bg_color} (tolerance: {args.tolerance}, mode: {args.mode})...")
    rgb = pixels[:, :, :3]
    target = np.array(bg_color, dtype=np.float64)
    dist = color_distance(rgb, target)

    all_matching = dist <= args.tolerance

    if args.mode == "global":
        # Remove ALL pixels matching the background color
        bg_mask = all_matching
    elif args.mode == "edge":
        bg_mask = flood_fill_edges(dist, args.tolerance)
    else:  # auto
        # Step 1: Edge flood fill at base tolerance
        bg_mask = flood_fill_edges(dist, args.tolerance)

        # Step 2: Also catch interior pockets at base tolerance
        interior_pockets = all_matching & ~bg_mask
        pocket_count = int(np.sum(interior_pockets))
        if pocket_count > 0:
            print(f"  Interior pockets: {pocket_count} pixels")
            bg_mask |= interior_pockets

        # Step 3: Expand mask boundary to catch fringe pixels at higher tolerance
        if args.expansion > 1.0:
            expanded_tol = args.tolerance * args.expansion
            pre_expand = int(np.sum(bg_mask))
            bg_mask = expand_mask_boundary(bg_mask, dist, expanded_tol)
            expanded = int(np.sum(bg_mask)) - pre_expand
            if expanded > 0:
                print(f"  Boundary expansion (+{expanded} fringe pixels at tolerance {expanded_tol:.0f})")

        # Step 4: Hue-based cleanup — catch washed-out/pastel variants of the bg color
        # (e.g., decorative borders Gemini draws in a lighter shade of the chroma key)
        pre_hue = int(np.sum(bg_mask))
        bg_mask = hue_cleanup(pixels, bg_mask, bg_color, hue_tolerance=30.0, min_saturation=0.15)
        hue_removed = int(np.sum(bg_mask)) - pre_hue
        if hue_removed > 0:
            print(f"  Hue cleanup (+{hue_removed} pixels matching bg hue)")

    bg_count = int(np.sum(bg_mask))
    total = img.width * img.height
    pct = 100 * bg_count / total
    print(f"Background pixels removed: {bg_count}/{total} ({pct:.1f}%)")

    if bg_count == 0:
        # Auto-investigate: Gemini likely drifted from the requested chroma-key color.
        # Sample edge pixels to detect the actual background color and retry.
        print("  0% removal detected — investigating actual background color...")
        detected = detect_actual_bg_color(pixels, bg_color)
        if detected is not None:
            det_hex = f"#{detected[0]:02X}{detected[1]:02X}{detected[2]:02X}"
            orig_hex = f"#{bg_color[0]:02X}{bg_color[1]:02X}{bg_color[2]:02X}"
            print(f"  Detected actual bg color: {det_hex} (expected {orig_hex})")
            print(f"  Retrying removal with detected color...")

            # Recompute distances with detected color
            bg_color = detected
            target = np.array(bg_color, dtype=np.float64)
            dist = color_distance(rgb, target)
            all_matching = dist <= args.tolerance

            if args.mode == "global":
                bg_mask = all_matching
            elif args.mode == "edge":
                bg_mask = flood_fill_edges(dist, args.tolerance)
            else:  # auto
                bg_mask = flood_fill_edges(dist, args.tolerance)
                interior_pockets = all_matching & ~bg_mask
                pocket_count = int(np.sum(interior_pockets))
                if pocket_count > 0:
                    print(f"  Interior pockets: {pocket_count} pixels")
                    bg_mask |= interior_pockets
                if args.expansion > 1.0:
                    expanded_tol = args.tolerance * args.expansion
                    pre_expand = int(np.sum(bg_mask))
                    bg_mask = expand_mask_boundary(bg_mask, dist, expanded_tol)
                    expanded = int(np.sum(bg_mask)) - pre_expand
                    if expanded > 0:
                        print(f"  Boundary expansion (+{expanded} fringe pixels at tolerance {expanded_tol:.0f})")
                pre_hue = int(np.sum(bg_mask))
                bg_mask = hue_cleanup(pixels, bg_mask, bg_color, hue_tolerance=30.0, min_saturation=0.15)
                hue_removed = int(np.sum(bg_mask)) - pre_hue
                if hue_removed > 0:
                    print(f"  Hue cleanup (+{hue_removed} pixels matching bg hue)")

            bg_count = int(np.sum(bg_mask))
            pct = 100 * bg_count / total
            print(f"  Retry result: {bg_count}/{total} ({pct:.1f}%)")

            if bg_count == 0:
                print("Warning: Still no background pixels matched after auto-detection. The output will be unchanged.", file=sys.stderr)
        else:
            print("Warning: Could not detect actual background color. The output will be unchanged.", file=sys.stderr)
    elif bg_count == total:
        print("Warning: ALL pixels matched as background. Try lowering --tolerance.", file=sys.stderr)

    # Build alpha channel
    alpha = pixels[:, :, 3].copy()
    alpha[bg_mask] = 0

    # Feather edges
    if args.feather > 0:
        # Dilate the bg_mask using numpy to find boundary pixels (no scipy needed)
        padded = np.pad(bg_mask, args.feather, mode="constant", constant_values=False)
        dilated = np.zeros_like(bg_mask)
        for dy in range(-args.feather, args.feather + 1):
            for dx in range(-args.feather, args.feather + 1):
                if dy * dy + dx * dx <= args.feather * args.feather:
                    shifted = padded[
                        args.feather + dy : args.feather + dy + bg_mask.shape[0],
                        args.feather + dx : args.feather + dx + bg_mask.shape[1],
                    ]
                    dilated |= shifted
        boundary = dilated & ~bg_mask
        # Blend alpha in boundary region
        feathered = feather_alpha(alpha, args.feather)
        alpha[boundary] = feathered[boundary]

    # Spill suppression: neutralize bg color from semi-transparent edge pixels
    pixels = suppress_spill(pixels, alpha, bg_color)

    pixels[:, :, 3] = alpha
    result = Image.fromarray(pixels, mode="RGBA")

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(str(output_path), "PNG")

    full_path = output_path.resolve()
    print(f"\nTransparent image saved: {full_path}")
    print(f"MEDIA: {full_path}")


if __name__ == "__main__":
    main()
