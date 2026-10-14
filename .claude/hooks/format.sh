#!/usr/bin/env bash
# PostToolUse hook: format/lint the file Claude just wrote or edited.
# Never blocks — every tool is optional and failures are ignored.

f=$(jq -r '.tool_input.file_path // empty')
[ -n "$f" ] && [ -f "$f" ] || exit 0

# Windows paths (D:\...) -> POSIX paths (/d/...) so dirname works under Git Bash
command -v cygpath >/dev/null 2>&1 && f=$(cygpath -u "$f")

root=${CLAUDE_PROJECT_DIR:-$(pwd)}
command -v cygpath >/dev/null 2>&1 && root=$(cygpath -u "$root")

case "${f##*.}" in
  py)
    # ruff picks up the nearest pyproject.toml (backend/pyproject.toml)
    command -v ruff >/dev/null 2>&1 && { ruff format "$f" || true; ruff check "$f"; }
    ;;
  ts|tsx|js|jsx|mjs|cjs|json|jsonc|css)
    # Biome is configured per package (frontend/, packages/react-email/):
    # run it from the directory holding the nearest biome.json.
    dir=$(dirname "$f")
    while [ "$dir" != "/" ] && [ "$dir" != "." ] && [ ! -f "$dir/biome.json" ]; do
      dir=$(dirname "$dir")
    done
    [ -f "$dir/biome.json" ] || exit 0

    biome=""
    for b in "$dir"/node_modules/.bin/biome{,.exe} "$root"/node_modules/.bin/biome{,.exe}; do
      [ -x "$b" ] && { biome=$b; break; }
    done
    [ -n "$biome" ] || exit 0

    # Relative path: works for both the shell shim and the native Windows biome.exe
    (cd "$dir" && "$biome" check --write --no-errors-on-unmatched --files-ignore-unknown=true "${f#"$dir"/}")
    ;;
esac

exit 0
