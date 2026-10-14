---
name: pr-review
description: Review the current branch (or a given branch) against main using the project's rules in .claude/rules/, and report findings by severity. Read-only. Use when the user asks to review a branch, PR, or merge request.
---

Review the changes on a branch before it's merged. Target: $ARGUMENTS (a branch name; defaults to the current branch). Base: `main`.

This is a read-only review: don't edit files, commit, push, or post comments anywhere.

## 1. Gather the change
- `git fetch origin main` if a remote exists (skip if it fails), then use `origin/main` as the base, falling back to `main`.
- `git log --oneline <base>..<target>` and `git diff --stat <base>...<target>`.
- Read the full diff (`git diff <base>...<target>`). For files where context matters, read the surrounding code too, not just the hunks.
- Skim generated files only to confirm they're there: `frontend/src/client/`, `src/routeTree.gen.ts`, `uv.lock`, `bun.lock`.

## 2. Check against the project rules
Read `.claude/rules/code-style.md`, `testing.md` and `workflow.md`, then check:

**Correctness and security** (highest priority)
- Logic bugs, unhandled `None`/empty cases, wrong status codes.
- Authorization: every new route uses `CurrentUser`. Owner/superuser checks match the `items.py` pattern, and admin routes use `get_current_active_superuser`.
- No secrets, no `.env` and no real credentials in `.env.example`.
- SQL goes through SQLModel `select(...)`, never string-built queries.
- Personal and memorial data (memories, voice, conversations of the deceased) isn't logged or returned to users who shouldn't see it.

**Completeness**
- Model change → Alembic migration included, and it matches the model.
- API change → regenerated `frontend/src/client/` included.
- New setting → added to `Settings` **and** `.env.example`.
- New endpoint → tests for the happy path, 404, 403 and 422. New UI flow → a Playwright spec.
- Anything that would push coverage below 90%.

**Conventions**
- Code style per `code-style.md` (type hints, route shape, TanStack Query/zod patterns, `@/` imports, theme tokens).
- Commit messages and branch name per `workflow.md`.
- Size: flag merge requests over ~400 changed lines (excluding generated files), and suggest how to split them.

## 3. Verify, if the tools are available
Run what's installed and report what you couldn't run, rather than guessing:
- `uv run prek run --from-ref <base> --to-ref <target>`, or `cd backend && uv run bash scripts/lint.sh`
- `bun run lint`
- Backend tests only if Postgres is up (`docker compose ps db`).

## 4. Report
Lead with a one-line verdict: **Approve**, **Approve with nits**, or **Request changes**.

Then the findings, grouped by severity:
- **Blocker**: bugs, security issues, missing migration/client/tests, broken builds
- **Should fix**: convention breaks, weak tests, missing edge cases
- **Nit**: naming and small readability points

For each finding, give `path:line`, what's wrong, why it matters and a concrete fix (a short snippet if that helps). Don't list things that are fine, and don't repeat what the linters already enforce unless they failed.

End with:
- **Checks run:** which commands ran and their result, and which were skipped and why.
- **Suggested MR description:** a short summary, how it was tested, and any migration or env-var changes. The user can paste it into GitLab.
