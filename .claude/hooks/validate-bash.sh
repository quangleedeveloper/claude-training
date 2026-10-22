#!/bin/bash
# Validate Bash commands before they run
# Hook: PreToolUse (matcher: Bash)
#
# Reads the tool call JSON from stdin and denies commands that break the
# project rules in .claude/rules/workflow.md or are destructive.
# Deny is reported with the PreToolUse hookSpecificOutput format.
#
# Compatible with: macOS, Linux, Windows (Git Bash)

# Read JSON input from stdin (Claude Code hook protocol)
INPUT=$(cat)

# Extract tool_input.command with sed (no jq/python dependency on Git Bash).
# The pattern accepts escaped characters so a command containing \" is not cut short.
COMMAND=$(printf '%s' "$INPUT" | sed -nE 's/.*"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' | head -1)

if [ -z "$COMMAND" ]; then
  exit 0
fi

deny() {
  # $1 = reason. Escape backslashes and double quotes for JSON.
  local reason
  reason=$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')
  printf '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "%s"}}' "$reason"
  exit 0
}

# Destructive system commands
DANGEROUS_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "rm -rf \*"
  "drop database"
  "drop table"
  "truncate table"
  "format disk"
  "mkfs"
  "dd if="
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if printf '%s' "$COMMAND" | grep -qi -- "$pattern"; then
    deny "Dangerous operation detected: $pattern"
  fi
done

# workflow.md: don't use --no-verify (prek must run on commit)
if printf '%s' "$COMMAND" | grep -qE 'git[[:space:]]+(commit|push|merge).*--no-verify'; then
  deny "Do not use --no-verify: prek hooks must run (see .claude/rules/workflow.md)."
fi

# workflow.md: main is protected, never push or force-push to it
if printf '%s' "$COMMAND" | grep -qE 'git[[:space:]]+push.*(--force|-f([[:space:]]|$)|--force-with-lease)'; then
  deny "Force push is not allowed."
fi
if printf '%s' "$COMMAND" | grep -qE 'git[[:space:]]+push([[:space:]]+[^[:space:]]+)?[[:space:]]+(HEAD:)?(refs/heads/)?main([[:space:]]|$)'; then
  deny "main is protected: push a feature branch and open a merge request."
fi

# workflow.md: never commit .env or other secrets
if printf '%s' "$COMMAND" | grep -qE 'git[[:space:]]+add.*(^|[[:space:]/])\.env([[:space:]]|$)'; then
  deny "Never commit .env: it holds secrets (see .claude/rules/workflow.md)."
fi

# Don't commit directly to main
if printf '%s' "$COMMAND" | grep -qE 'git[[:space:]]+commit'; then
  BRANCH=$(git branch --show-current 2>/dev/null)
  if [ "$BRANCH" = "main" ]; then
    deny "Never commit to main directly: create a <type>/<name> branch first."
  fi
fi

# Production deployments need the approval file, same gate as validate-prompt.sh
if printf '%s' "$COMMAND" | grep -qiE '(deploy|push).*production|compose\.deploy\.yml'; then
  if [ ! -f ".deployment-approved" ]; then
    deny "Production deployment requires approval. Create .deployment-approved file to proceed."
  fi
fi

exit 0
