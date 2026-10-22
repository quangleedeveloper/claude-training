#!/bin/bash
# Initialize subagents with project context
# Hook: SubagentStart
#
# Injects the key project rules into every subagent so it starts with the same
# constraints as the main session. Non-blocking: only adds additionalContext.
#
# Compatible with: macOS, Linux, Windows (Git Bash)

# Read JSON input from stdin (Claude Code hook protocol); not used yet, but
# drain it so the caller never blocks on a full pipe.
cat > /dev/null

CONTEXT="Project: Memorial Robot (FastAPI + SQLModel backend, React + TypeScript frontend). Follow .claude/rules/. Never commit .env or secrets, never commit or push to main, and never use --no-verify. Do not hand-edit frontend/src/client/. AI/LLM calls in tests must use a fake client."

printf '{"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": "%s"}}' "$CONTEXT"

exit 0
