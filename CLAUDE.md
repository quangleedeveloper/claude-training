# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Memorial Robot** — an AI robot designed to preserve memories and simulate the conversational abilities of the deceased.

Built on [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template): FastAPI + SQLModel + PostgreSQL backend, React + TypeScript + Vite frontend, run with Docker Compose. The template's sample `Item` model and pages are still in place. The repo also carries a curated set of Claude Code commands, skills, and hooks.

## Directory Structure

- `backend/` — FastAPI app (uv workspace member)
  - `app/main.py` — app entrypoint; `app/api/routes/` — endpoints (`items`, `login`, `users`, `utils`, `private`)
  - `app/models.py` — SQLModel tables and API schemas; `app/crud.py` — DB operations
  - `app/core/` — config (reads root `.env`), DB engine, security
  - `app/alembic/` — migrations; `tests/` — Pytest suite; `scripts/` — prestart/test/lint/format
- `frontend/` — React app (bun workspace): TanStack Router file routes in `src/routes/`, generated API client in `src/client/` (do not hand-edit), Playwright tests in `tests/`
- `packages/react-email/` — email templates, exported to `backend/app/email-templates/`
- `compose.yml` / `compose.override.yml` (local dev) / `compose.deploy.yml` — Docker Compose stacks
- `.env.example` — tracked config defaults (incl. `PROJECT_NAME`); copy to `.env` (gitignored), which the backend and compose read. Replace every `changethis` secret before deploying
- `.claude/commands/` — Custom slash commands (e.g., `/optimize`)
- `.claude/skills/` — Skills invoked automatically by Claude or via slash commands
- `.claude/agents/` — Subagents (e.g., `code-improver`: read-only, Sonnet-powered code improvement suggestions)
- `.claude/settings.json` — Team-shared hooks and permissions (commit this file)
- `.claude/hooks/format.sh` — PostToolUse hook: after Write/Edit, runs ruff on `.py` and Biome (from the nearest `biome.json` package) on TS/JS/JSON/CSS; tools that aren't installed are skipped

## Common Commands

```bash
# First time: cp .env.example .env
# Full stack (app at http://localhost:8000, docs at /docs, Mailpit at :8025, Adminer at :8080)
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch

# Local backend (from backend/, with `docker compose up -d db mailpit` running)
uv sync
uv run bash scripts/prestart.sh   # wait for DB, run migrations, seed superuser
uv run fastapi dev                # http://localhost:8000
uv run bash scripts/test.sh       # Pytest + coverage
uv run alembic revision --autogenerate -m "<message>"   # after changing models.py

# Local frontend (from repo root)
bun install
bun run dev                       # http://localhost:5173
bun run lint                      # Biome
bun run test                      # Playwright (needs the stack running)
bun run --filter frontend generate-client   # regenerate src/client after API changes (backend running)

# All pre-commit checks
uv run prek run --all-files
```

See `development.md`, `backend/README.md`, `frontend/README.md`, and `deployment.md` for details.

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

## Conventions

See `.claude/rules/` for code style (`code-style.md`), testing (`testing.md`), and branch/commit/MR workflow (`workflow.md`).
