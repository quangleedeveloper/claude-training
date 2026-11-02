#!/bin/bash
# Security scan on file write
# Hook: PostToolUse (matcher: Write|Edit)
#
# Scans files for hardcoded secrets, API keys, and credentials.
# Outputs a non-blocking warning via additionalContext when issues are found.
#
# Compatible with: macOS, Linux, Windows (Git Bash)

# Read JSON input from stdin (Claude Code hook protocol)
INPUT=$(cat)

# Extract file_path using sed (compatible with all platforms including Windows Git Bash)
# Avoids grep -P (not available on Windows Git Bash) and python3 dependency
FILE_PATH=$(printf '%s' "$INPUT" | sed -nE 's/.*"file_path"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' | head -1)
# Undo JSON escaping (Windows paths arrive as D:\\code\\...), then use a POSIX path under Git Bash
FILE_PATH=$(printf '%s' "$FILE_PATH" | sed 's/\\"/"/g; s/\\\\/\\/g')
if command -v cygpath &> /dev/null; then
  FILE_PATH=$(cygpath -u "$FILE_PATH" 2>/dev/null || printf '%s' "$FILE_PATH")
fi

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# Skip binary files, vendor dirs, and build artifacts
case "$FILE_PATH" in
  *.png|*.jpg|*.jpeg|*.gif|*.svg|*.ico|*.woff|*.woff2|*.ttf|*.eot) exit 0 ;;
  */node_modules/*|*/.git/*|*/dist/*|*/build/*) exit 0 ;;
esac

ISSUES=""

# Check for hardcoded passwords
# Handles both JSON format ("password": "value") and code format (password = 'value')
# Use \\n as separator — it is a valid JSON newline escape and passes through printf safely
if grep -qiE '"password"[[:space:]]*:[[:space:]]*"[^"]+"' "$FILE_PATH" 2>/dev/null; then
  ISSUES="${ISSUES}- WARNING: Potential hardcoded password detected\\n"
elif grep -qiE '(password|passwd|pwd)[[:space:]]*=[[:space:]]*'"'"'[^'"'"']+'"'"'' "$FILE_PATH" 2>/dev/null; then
  ISSUES="${ISSUES}- WARNING: Potential hardcoded password detected\\n"
fi

# Check for hardcoded API keys
if grep -qiE '"(api[_-]?key|apikey|access[_-]?token)"[[:space:]]*:[[:space:]]*"[^"]+"' "$FILE_PATH" 2>/dev/null; then
  ISSUES="${ISSUES}- WARNING: Potential hardcoded API key detected\\n"
fi

# Check for hardcoded secrets and tokens
if grep -qiE '(secret|token)[[:space:]]*=[[:space:]]*['"'"'"][^'"'"'"]+['"'"'"]' "$FILE_PATH" 2>/dev/null; then
  ISSUES="${ISSUES}- WARNING: Potential hardcoded secret or token detected\\n"
fi

# Check for private keys
if grep -q "BEGIN.*PRIVATE KEY" "$FILE_PATH" 2>/dev/null; then
  ISSUES="${ISSUES}- WARNING: Private key detected\\n"
fi

# Check for AWS keys
if grep -qE "AKIA[0-9A-Z]{16}" "$FILE_PATH" 2>/dev/null; then
  ISSUES="${ISSUES}- WARNING: AWS access key detected\\n"
fi

# Bound the external scanners so an edit never hangs on a slow rule download
run_scanner() {
  if command -v timeout &> /dev/null; then
    timeout 20 "$@" >/dev/null 2>&1
  else
    "$@" >/dev/null 2>&1
  fi
}

# Scan with semgrep if available. --error makes findings exit 1; a timeout (124)
# or tool failure is not a finding.
if command -v semgrep &> /dev/null; then
  run_scanner semgrep --config=auto --metrics=off --error --quiet "$FILE_PATH"
  if [ $? -eq 1 ]; then
    ISSUES="${ISSUES}- WARNING: semgrep reported findings\\n"
  fi
fi

# Scan with trufflehog if available. --fail exits 183 when secrets are found.
if command -v trufflehog &> /dev/null; then
  run_scanner trufflehog filesystem "$FILE_PATH" --only-verified --fail --no-update
  if [ $? -eq 183 ]; then
    ISSUES="${ISSUES}- WARNING: trufflehog found verified secrets\\n"
  fi
fi

# If issues found, output as additionalContext (non-blocking warning)
# Use hookSpecificOutput format required by Claude Code PostToolUse protocol
if [ -n "$ISSUES" ]; then
  # Escape file path for JSON (backslash and double-quote)
  # ISSUES already uses \\n as separator (valid JSON escape) — only escape double-quotes
  SAFE_PATH=$(printf '%s' "$FILE_PATH" | sed 's/\\/\\\\/g; s/"/\\"/g')
  SAFE_ISSUES=$(printf '%s' "$ISSUES" | sed 's/"/\\"/g')
  printf '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "Security scan found issues in %s:\\n%sPlease review and use environment variables instead."}}' "$SAFE_PATH" "$SAFE_ISSUES"
else
  # systemMessage is shown to the user in the terminal; plain stdout would not be
  printf '{"systemMessage": "Security Ok"}'
fi

exit 0
