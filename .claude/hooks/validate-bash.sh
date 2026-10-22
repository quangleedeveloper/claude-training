#!/bin/bash
# Validate Bash commands before they run
# Hook: PreToolUse (matcher: Bash)
#
# Reads the tool call JSON from stdin and denies commands that break the
# project rules in .claude/rules/workflow.md or are destructive.
# Deny is reported with the PreToolUse hookSpecificOutput format.
#
# Compatible with: macOS, Linux, Windows (Git Bash)

# Shared production-deploy gate
source "$(dirname "${BASH_SOURCE[0]}")/deploy-gate.sh"

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

# Undo JSON string escaping. A tab or newline arrives as \t or \n; left escaped, the
# [[:space:]] and line-start (^) matching below would not see them as separators and
# `git<TAB>push<TAB>origin<TAB>main` would slip past every rule. The real newline this
# produces is a command boundary because grep matches line by line. Pure bash expansion
# (no GNU-only sed escapes) so it behaves the same on Git Bash, Linux and macOS. \\ goes
# through a placeholder so an escaped backslash is not read as the start of another escape.
BS='\'
MARK=$'\x01'
decoded=$COMMAND
decoded=${decoded//"$BS$BS"/$MARK}
decoded=${decoded//"${BS}u0009"/$'\t'}
decoded=${decoded//"${BS}u000a"/$'\n'}
decoded=${decoded//"${BS}u000A"/$'\n'}
decoded=${decoded//"${BS}t"/$'\t'}
decoded=${decoded//"${BS}n"/$'\n'}
# \r is an ordinary character in bash, not a separator, so it becomes a space.
decoded=${decoded//"${BS}r"/ }
decoded=${decoded//"${BS}\""/\"}
decoded=${decoded//"${BS}/"/\/}
decoded=${decoded//"$MARK"/"$BS"}

# Bash joins a backslash-newline pair into one line, so `git push \<NL> origin main` is one
# command, and the line-by-line matching below would miss `main` if it stayed split.
#
# Walk the text the way bash reads it so the join happens exactly where bash joins: a
# backslash escapes the next character (a newline after it vanishes), single quotes are
# literal, and a # that starts a word begins a comment that ends at the newline even when
# it ends in a backslash.
joined=''
in_single=0
in_double=0
in_comment=0
length=${#decoded}
i=0
while [ "$i" -lt "$length" ]; do
  ch=${decoded:i:1}
  i=$(( i + 1 ))
  if [ "$in_comment" -eq 1 ]; then
    [ "$ch" = $'\n' ] && in_comment=0
    joined+=$ch
  elif [ "$in_single" -eq 1 ]; then
    [ "$ch" = "'" ] && in_single=0
    joined+=$ch
  elif [ "$ch" = '\' ]; then
    next=${decoded:i:1}
    i=$(( i + 1 ))
    [ "$next" = $'\n' ] || joined+=$ch$next
  elif [ "$in_double" -eq 1 ]; then
    [ "$ch" = '"' ] && in_double=0
    joined+=$ch
  elif [ "$ch" = "'" ]; then
    in_single=1
    joined+=$ch
  elif [ "$ch" = '"' ]; then
    in_double=1
    joined+=$ch
  elif [ "$ch" = '#' ]; then
    # Only a # at the start of a word is a comment; $#, ${#x} and a#b are not.
    prev=${joined: -1}
    case "$prev" in
      ''|' '|$'\t'|$'\n'|';'|'&'|'|'|'(') in_comment=1 ;;
    esac
    joined+=$ch
  else
    joined+=$ch
  fi
done
COMMAND=$joined

# Fail closed: the normalization above must never turn a command into nothing.
if [ -z "$COMMAND" ]; then
  deny "Could not parse the Bash command safely: refusing to run it unchecked."
fi

# The rules run on the joined text and, as defense in depth, on the unjoined text too: the
# scanner above is a simplified model of bash quoting (it does not know $'..' strings, for
# one), so if its quote state ever drifts, the split form still catches what it hid.
# Either form matching denies.
check_rules() {
  local COMMAND=$1

  # Command boundary: start of line or after ; & | so patterns match commands,
  # not text inside a commit message or grep argument.
  BOUNDARY='(^|[;&|][[:space:]]*)'
  # Anything between words of one command, never crossing into the next one.
  SAME_CMD='[^;&|]*'

  # Destructive system commands
  DANGEROUS_PATTERNS=(
    "${BOUNDARY}rm[[:space:]]+-rf[[:space:]]+(/|~|\*)([[:space:]]|\$)"
    "${BOUNDARY}mkfs(\.[a-z0-9]+)?([[:space:]]|\$)"
    "${BOUNDARY}dd[[:space:]]+${SAME_CMD}if="
    "${BOUNDARY}format[[:space:]]+disk"
    # SQL only counts when a database client runs it
    "${BOUNDARY}(psql|mysql|sqlite3|sqlcmd)[[:space:]]+${SAME_CMD}(drop[[:space:]]+(database|table)|truncate[[:space:]]+table)"
  )

  for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if printf '%s' "$COMMAND" | grep -qiE -- "$pattern"; then
      deny "Dangerous operation detected in command."
    fi
  done

  # workflow.md: don't use --no-verify (prek must run on commit)
  # Covers -n (short for --no-verify on commit), git -C <dir>, and core.hooksPath overrides.
  GIT_ANY="git[[:space:]]+(${SAME_CMD}[[:space:]])?"
  if printf '%s' "$COMMAND" | grep -qE "${GIT_ANY}(commit|push|merge)[[:space:]]${SAME_CMD}--no-verify"; then
    deny "Do not use --no-verify: prek hooks must run (see .claude/rules/workflow.md)."
  fi
  if printf '%s' "$COMMAND" | grep -qE "${GIT_ANY}commit([[:space:]]${SAME_CMD})?[[:space:]]-[a-zA-Z]*n[a-zA-Z]*([[:space:]]|\$)"; then
    deny "Do not use -n (--no-verify): prek hooks must run (see .claude/rules/workflow.md)."
  fi
  if printf '%s' "$COMMAND" | grep -qE "git[[:space:]]+${SAME_CMD}core\.hooksPath"; then
    deny "Do not override core.hooksPath: prek hooks must run (see .claude/rules/workflow.md)."
  fi

  # workflow.md: main is protected, never push or force-push to it
  if printf '%s' "$COMMAND" | grep -qE "${GIT_ANY}push[[:space:]]${SAME_CMD}(--force|-f([[:space:]]|\$)|--force-with-lease)"; then
    deny "Force push is not allowed."
  fi
  # Any refspec that ends on main: `origin main`, `-u origin main`, `+main`, `x:main`, `HEAD:refs/heads/main`.
  if printf '%s' "$COMMAND" | grep -qE "${GIT_ANY}push[[:space:]]${SAME_CMD}[[:space:]]\+?([^[:space:];&|:]*:)?(refs/heads/)?main([[:space:]]|\$)"; then
    deny "main is protected: push a feature branch and open a merge request."
  fi

  # workflow.md: never commit .env or other secrets
  if printf '%s' "$COMMAND" | grep -qE 'git[[:space:]]+add.*(^|[[:space:]/])\.env([[:space:]]|$)'; then
    deny "Never commit .env: it holds secrets (see .claude/rules/workflow.md)."
  fi

  # Don't commit directly to main. Only judge the current branch when the command
  # runs `git commit` itself and does not first change branch or directory.
  if printf '%s' "$COMMAND" | grep -qE "${BOUNDARY}git[[:space:]]+commit"; then
    if ! printf '%s' "$COMMAND" | grep -qE "(switch|checkout)[[:space:]]+${SAME_CMD}-[cbCB]([[:space:]]|\$)|git[[:space:]]+-C[[:space:]]|${BOUNDARY}cd[[:space:]]"; then
      BRANCH=$(git branch --show-current 2>/dev/null)
      if [ "$BRANCH" = "main" ]; then
        deny "Never commit to main directly: create a <type>/<name> branch first."
      fi
    fi
  fi

  # Production deployments need the approval file, same gate as validate-prompt.sh
  if printf '%s' "$COMMAND" | grep -qiE "${BOUNDARY}(\./|bash |sh |make |docker |kubectl |ssh )${SAME_CMD}(deploy|push)${SAME_CMD}production|docker[[:space:]]+compose${SAME_CMD}compose\.deploy\.yml"; then
    if ! deployment_approved; then
      deny "$DEPLOY_APPROVAL_MESSAGE"
    fi
  fi
}

check_rules "$COMMAND"
check_rules "$decoded"

exit 0
