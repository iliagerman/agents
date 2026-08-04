#!/usr/bin/env bash
set -uo pipefail

scope=${*:-Review staged and unstaged changes; if the working tree is clean, review the current branch against its default base branch.}
output=$(mktemp)
pid=
cleanup() {
  [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true
  rm -f "$output"
}
trap cleanup EXIT INT TERM

prompt="Review the code changes in this repository. Scope: $scope Read applicable project instructions and inspect changed files in context. Do not modify files. Focus on correctness, security, regressions, performance, maintainability, and missing tests. Report only actionable findings, ordered by severity, with exact file paths and line numbers. For each finding explain the impact and the smallest sound fix. If no findings exist, say so explicitly."

pi -p --no-session --approve \
  --model openai-codex/gpt-5.6-sol \
  --tools read,bash \
  "$prompt" >"$output" 2>&1 &
pid=$!

printf 'Pi review started (PID %s).\n' "$pid"
started=$SECONDS
while kill -0 "$pid" 2>/dev/null; do
  sleep 15
  kill -0 "$pid" 2>/dev/null && printf 'Pi review running: %ss elapsed.\n' "$((SECONDS - started))"
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
