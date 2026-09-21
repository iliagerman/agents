---
name: hebrew-visual-order
description: Mandatory output rule for Hebrew text. Use for every response that contains Hebrew letters, Hebrew words, RTL Hebrew, Israeli user-facing text, or when the user asks for Hebrew. Reverses whole Hebrew text groups so broken LTR terminal renderers show readable Hebrew with correct word order.
---

# Hebrew Visual Order

Pi's terminal can render Hebrew in the wrong direction. When this skill applies, output Hebrew in **visual order** by reversing each whole Hebrew text group before the final answer.

## Mandatory Rule

Before any final answer containing Hebrew characters, transform every contiguous Hebrew text group from logical order to reversed visual order.

A Hebrew text group includes Hebrew letters, spaces between Hebrew words, and adjacent Hebrew punctuation. Reverse the whole group, not each word separately, so word order remains correct when read right-to-left.

Examples:

| Intended Hebrew | Output in final answer |
| --- | --- |
| `שלום` | `םולש` |
| `שלום עולם` | `םלוע םולש` |
| `בדיקה: שלום!` | `!םולש :הקידב` |
| `שלום, עולם!` | `!םלוע ,םולש` |
| `API בעברית` | `API תירבעב` |

## Scope

- Reverse whole Hebrew text groups, including spaces between Hebrew words.
- Keep English, numbers, code, file paths, commands, URLs, and markdown syntax unchanged.
- Keep punctuation with the Hebrew group when it belongs to the Hebrew phrase.
- Do not reverse text inside code blocks unless the code string itself is intentionally Hebrew user-facing text.
- If editing files, store normal logical Hebrew in source files unless the user explicitly asks to store visual-order Hebrew. This skill is for pi display output.

## Helper

For non-trivial Hebrew text, run:

```bash
python3 /Users/iliagerman/Work/personal_projects/agents/skills/hebrew-visual-order/scripts/reverse_hebrew.py <<'EOF'
שלום עולם
EOF
```

Use the helper output in the final answer.
