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
- `.claude/hooks/protect-paths.sh` — PreToolUse hook: blocks agents from `backend/uploads/` (real family media) and, while `.claude/tests-locked` exists, from editing tests, `evals/` and `fixtures/`
- `intent/`, `specs/<feature>/`, `tickets/`, `qa/`, `evals/grounding/`, `fixtures/` — delivery artifacts (see *Delivery flow*); each folder has a README
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

## Memorial Robot must-knows

- **Answers come only from the family's memories.** Retrieval (`app/services/retrieval.py`) skips rejected items and is scoped to the caller's own memories; `all_users` is superuser-only.
- **No context, no model call.** If nothing clears `MIN_RELEVANCE_SCORE`, return the fixed `NO_ANSWER` (`app/services/ask_graph.py`). Every answer returns the memories it used (`AskResponse.sources`), cited as `[n]`.
- **AI stays local.** Ollama + Whisper behind `LLMClient` / `Transcriber`. Never add a hosted AI API or send memory text or media off the machine. Tests use `app/core/fake_ai.py`.
- **Prompts live only in `app/core/prompt.py`.** Uploaded stories are data, never instructions.
- **No memory content in logs or error details**: log IDs and counts only.
- **Corrections win.** `was_edited` items keep the family's wording through re-extraction.
- **Real uploads are off-limits** (`backend/uploads/`, hook-enforced). Use synthetic data from `fixtures/` and `backend/tests/utils/`.
- Details and checklists: the `grounding-policy` and `memorial-privacy` skills.

## Delivery flow (AI-native SDLC)

brief in `tickets/MR-<n>.md` (verbatim) → `intent/<feature>.md` → `specs/<feature>/spec.md` (FR/AC IDs) → tickets `tickets/MR-<n>.md` → `qa/test-matrix.md` + `evals/grounding/` → plan mode `specs/<feature>/plans/MR-<n>.md` → PR reviewed per `REVIEW.md`.

- Use the `ba-intake` skill and its templates for intent, spec, tickets and the test matrix.
- **Questions go only in the ticket's `## Questions` section**; the answer updates `spec.md` in the same PR.
- Before reporting a ticket done, run the `verifier` subagent.
- Bug fixes: commit the failing test, `touch .claude/tests-locked`, fix the code, then delete the lock.

## Conventions

See `.claude/rules/` for code style (`code-style.md`), testing (`testing.md`), and branch/commit/MR workflow (`workflow.md`).
