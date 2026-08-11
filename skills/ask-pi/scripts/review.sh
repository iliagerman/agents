#!/usr/bin/env bash
set -uo pipefail

scope=${*:-Review staged and unstaged changes; if the working tree is clean, review the current branch against its default base branch.}
thinking=${PI_REVIEW_THINKING:-high}
case "$thinking" in
  off|minimal|low|medium|high|xhigh|max) ;;
  *) printf 'Invalid PI_REVIEW_THINKING: %s\n' "$thinking" >&2; exit 2 ;;
esac
output=$(mktemp)
pid=
cleanup() {
  [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true
  rm -f "$output"
}
trap cleanup EXIT INT TERM

prompt="Review the code changes in this repository. Scope: $scope Read applicable project instructions and inspect changed files in context. Do not modify files. Focus on correctness, security, regressions, performance, maintainability, and missing tests. Report only actionable findings, ordered by severity, with exact file paths and line numbers. For each finding explain the impact and the smallest sound fix. If no findings exist, say so explicitly."

pi -p --no-session --no-extensions --offline --approve \
  --model openai-codex/gpt-5.6-sol \
  --thinking "$thinking" \
  --tools read,bash \
  "$prompt" >"$output" 2>&1 &
pid=$!

printf 'Pi review started (PID %s).\n' "$pid"
started=$SECONDS
while kill -0 "$pid" 2>/dev/null; do
  sleep 15
  elapsed=$((SECONDS - started))
  if ((elapsed >= 900)); then
    kill -KILL "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    pid=
    cat "$output" >&2
    printf 'Pi review timed out after 900s.\n' >&2
    exit 124
  fi
  kill -0 "$pid" 2>/dev/null && printf 'Pi review running: %ss elapsed.\n' "$elapsed"
done

if wait "$pid"; then
  pid=
  cat "$output"
else
  status=$?
  pid=
  cat "$output" >&2
  exit "$status"
fi
