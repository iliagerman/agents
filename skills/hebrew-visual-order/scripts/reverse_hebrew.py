#!/usr/bin/env python3
"""Reverse Hebrew text groups for terminals that render RTL text incorrectly."""

import re
import sys

HEBREW_GROUP = re.compile(
    r"[\u0590-\u05FF](?:[\u0590-\u05FF \t,.:;!?״׳\"'()\[\]{}\-–—/\\]*[\u0590-\u05FF])?[,.!?;:״׳\"')\]}]*"
)


def reverse_hebrew_groups(text: str) -> str:
    return HEBREW_GROUP.sub(lambda match: match.group(0)[::-1], text)


def main() -> None:
    sys.stdout.write(reverse_hebrew_groups(sys.stdin.read()))


if __name__ == "__main__":
    main()
