#!/bin/bash
# Validate user prompts
# Hook: UserPromptSubmit
#
# Reads the user prompt from stdin JSON and blocks dangerous operations.
#
# Compatible with: macOS, Linux, Windows (Git Bash)

# Shared production-deploy gate
source "$(dirname "${BASH_SOURCE[0]}")/deploy-gate.sh"

# Read JSON input from stdin (Claude Code hook protocol)
INPUT=$(cat)

# Extract the prompt text from JSON input
# Claude Code sends the UserPromptSubmit text in the "prompt" field
# Accept escaped characters so a prompt containing \" is not cut short. An escaped
# "prompt" inside the text can't match, so the greedy prefix lands on the real field.
PROMPT=$(printf '%s' "$INPUT" | sed -nE 's/.*"prompt"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' | head -1)


if [ -z "$PROMPT" ]; then
  exit 0
fi

# Check for dangerous operations
DANGEROUS_PATTERNS=(
  "rm -rf /"
  "delete database"
  "drop database"
  "format disk"
  "dd if="
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$PROMPT" | grep -qi "$pattern"; then
    printf '{"decision": "block", "reason": "Dangerous operation detected: %s"}' "$pattern"
    exit 0
  fi
done

# Check for production deployments
if echo "$PROMPT" | grep -qiE "(deploy|push).*production"; then
  if ! deployment_approved; then
    printf '{"decision": "block", "reason": "%s"}' "$DEPLOY_APPROVAL_MESSAGE"
    exit 0
  fi
fi

# Check for required context in certain operations
if echo "$PROMPT" | grep -qi "refactor"; then
  if [ ! -d "tests" ] && [ ! -d "test" ]; then
    printf '{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "Warning: Refactoring without tests may be risky. Consider writing tests first."}}'
  fi
fi

exit 0
