# Workflow

## Branches
- `main` is the default and protected branch. Never commit to it directly.
- Branch names: `<type>/<short-kebab-description>`, e.g. `feat/rebrand-memorial-robot`, `fix/email-utf8-encoding`.

## Commits: Conventional Commits
- `<type>: <imperative summary>` (≤72 chars, lowercase, no period). Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `build`.
- One logical change per commit. Include the generated client (`frontend/src/client/`) and Alembic migrations in the same commit as the change that produced them.
- prek runs on commit. If it rewrites files, `git add` them and commit again. Don't use `--no-verify`.

## Typical feature flow
1. `git switch -c feat/<name>` from an up-to-date `main`.
2. Backend:
   - change `app/models.py` → `uv run alembic revision --autogenerate -m "..."` → review the migration
   - `crud.py` / route → tests
3. Regenerate the client: `bun run --filter frontend generate-client` (backend running). The prek hook also does this.
4. Frontend: components, routes and Playwright specs.
5. New config: add it to `Settings` **and** `.env.example`, and mention it in the PR.
6. Run the checks in `testing.md`. Then push and open a merge request against `main`.

## Merge requests (GitLab: origin is gitlab.asoft-python.com)
- Title in Conventional Commit format. Description: what and why, how it was tested, screenshots for UI, and the migration and env-var changes. The template in `.github/pull_request_template.md` has a section for each.
- **Screenshots are required when the UI changes**: the main state, an empty or error state, and before/after for a changed screen. Attach them to the description; write "No UI change" otherwise.
  - Get them with `PR_SCREENSHOTS=1 bunx playwright test <spec>` (full-page PNGs in `frontend/test-results/`), or from the `pr-screenshots-*` artifacts of the PR's Playwright run (kept 14 days).
  - Only synthetic data: never real family media or text (`backend/uploads/` is off-limits).
- Keep MRs small (aim for under ~400 changed lines, excluding generated files).
- At least one approval. Squash-merge into `main`.

## CI
- `.github/workflows/` comes from the template and **does not run on GitLab**. Decision pending: port the jobs to `.gitlab-ci.yml`, or delete `.github/`.
  - Jobs worth porting: pre-commit, backend tests + 90% coverage, Playwright, docker-compose smoke test.

## Working with Claude Code
- Start non-trivial work in plan mode (Shift+Tab). Approve the plan before any edits.
- Use `/commit-message` to draft a commit message and `/pr-review` to review a branch against `main` (`.claude/skills/`).
- Ask Claude to commit or push explicitly. It doesn't do either on its own.
- Never commit `.env`, `CLAUDE.local.md` content or secrets.
