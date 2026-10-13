# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code configuration template — a curated set of commands, skills, and hooks designed to be reused and extended across projects.

## Directory Structure

- `.claude/commands/` — Custom slash commands (e.g., `/optimize`)
- `.claude/skills/` — Skills invoked automatically by Claude or via slash commands
- `.claude/settings.json` — Team-shared hooks and permissions (commit this file)

## Authoring Commands

Commands live in `.claude/commands/<name>.md`. Reference `optimize.md` as the canonical example. Required frontmatter:

```yaml
---
description: <one-line description>
---
```

- Use `$ARGUMENTS` in the body to accept user input (e.g., `/optimize <file>`)
- Add `disable-model-invocation: true` for commands with side effects so only the user can trigger them

## Authoring Skills

Skills live in `.claude/skills/<name>/SKILL.md`. Required frontmatter:

```yaml
---
name: <skill-name>
description: <what it does and when to use it>
---
```

- Skills run on-demand (user types `/<name>`) or auto-trigger when Claude detects a match
- Add `disable-model-invocation: true` for skills with side effects

## Python

- Formatter: `ruff format <file>`
- Linter: `ruff check <file>`
- Configure via `pyproject.toml` `[tool.ruff]` section

## TypeScript / JavaScript

- Formatter: `prettier --write <file>`
- Linter: `eslint <file>`
- Configure via `.prettierrc` and `.eslintrc` (or `eslint.config.js`)
