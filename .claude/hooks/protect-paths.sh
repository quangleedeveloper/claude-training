#!/bin/bash
# Protect family data and locked tests
# Hook: PreToolUse (matcher: Read|Write|Edit|MultiEdit|NotebookEdit|Grep|Glob)
#
# 1. backend/uploads/ holds real family media (memorial-privacy skill): agents never
#    read or write it. Use synthetic data from fixtures/ instead.
# 2. While .claude/tests-locked exists, tests, eval cases and fixtures can't be
#    edited. Create it once a bug's failing test is committed, so the fix changes
#    the code and not the test; delete it when the fix is done.
# Bash commands that name backend/uploads are denied in validate-bash.sh.
#
# Compatible with: macOS, Linux, Windows (Git Bash)

INPUT=$(cat)

# Read one string field from the hook JSON (sed only: no jq/python on Git Bash).
# The greedy prefix lands on the last occurrence, which is the tool_input field.
field() {
  printf '%s' "$INPUT" | sed -nE 's/.*"'"$1"'"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' | head -1
}

# JSON-escaped Windows paths (D:\\code\\x) -> d:/code/x, so one pattern fits all OSes
normalize() {
  printf '%s' "$1" | sed 's/\\\\/\\/g' | tr '\\' '/' | tr -s '/' | tr '[:upper:]' '[:lower:]'
}

deny() {
  local reason
  reason=$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')
  printf '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "%s"}}' "$reason"
  exit 0
}

TOOL=$(field tool_name)

for raw in "$(field file_path)" "$(field notebook_path)" "$(field path)" "$(field pattern)"; do
  [ -n "$raw" ] || continue
  p=$(normalize "$raw")

  if printf '%s' "$p" | grep -qE '(^|/)backend/uploads(/|$)'; then
    deny "backend/uploads/ holds real family media and is off-limits to agents. Use synthetic data from fixtures/ (see the memorial-privacy skill)."
  fi

  case "$TOOL" in
    Write|Edit|MultiEdit|NotebookEdit)
      root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
      if [ -f "${root:-.}/.claude/tests-locked" ] &&
        printf '%s' "$p" | grep -qE '(^|/)(backend/tests|frontend/tests|evals|fixtures)/'; then
        deny "Tests are locked for this fix (.claude/tests-locked exists): make the failing test pass by changing the code, not the test. Delete the lock file to unlock."
      fi
      ;;
  esac
done

exit 0
