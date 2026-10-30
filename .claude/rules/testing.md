# Testing

## Backend: Pytest (backend/tests/)
- Run: `cd backend && uv run bash scripts/test.sh`. Needs `docker compose up -d db mailpit` and `uv run bash scripts/prestart.sh` first.
  - Single test: `uv run pytest tests/api/routes/test_items.py::test_read_item -x`.
- Coverage gate: CI fails below **90%** (`coverage report --fail-under=90`). New code ships with tests.
- Layout mirrors `app/`: `tests/api/routes/test_<resource>.py`, `tests/crud/test_<model>.py`.
- Tests run against the **real Postgres DB**, with no mocks for the database.
  - The session-scoped `db` fixture (`tests/conftest.py`) seeds the superuser and deletes all `Item`/`User` rows at the end.
  - Clean up after yourself if a test leaves state other tests would see.
- Fixtures to reuse: `client`, `db`, `superuser_token_headers`, `normal_user_token_headers`.
- Factories: `tests/utils/` (`create_random_item`, `create_random_user`, `random_email`, `random_lower_string`). Add a `tests/utils/<model>.py` factory for each new model.
- Test names: `test_<action>_<resource>[_<case>]`, e.g. `test_read_item_not_found`, `test_read_item_not_enough_permissions`.
- Each endpoint covers: the happy path, 404, 403 (normal user vs. owner/superuser) and validation (422). Assert the status code, then the body fields and the `detail` message.
- URLs: build them with `f"{settings.API_V1_STR}/..."`, never hard-coded.
- Emails: don't send them. Patch `app.utils.send_email` or assert through Mailpit.
- **(new)** AI/LLM calls (conversation simulation): put them behind a small client interface and use a fake in tests. Tests must never call a paid external API.

## Frontend: Playwright E2E (frontend/tests/)
- Run: `bun run test` (the stack must be running). Debug with `bunx playwright test --ui`.
- `auth.setup.ts` logs in once and saves `playwright/.auth/user.json`, which most specs reuse.
  - For a fresh user: `test.use({ storageState: { cookies: [], origins: [] } })` + `createUser()` from `utils/privateApi.ts` + `logInUser()`.
- Test data: helpers from `utils/random.ts`, so tests can run in parallel (`fullyParallel: true`).
- Selectors: `getByRole`, `getByLabel`, `getByText`. No CSS/XPath selectors and no `waitForTimeout`; rely on `expect(...).toBeVisible()` auto-waiting.
- Emails (signup, password reset): read them through `utils/mailpit.ts`.
- One spec file per feature (`items.spec.ts`, `login.spec.ts`). Test names are sentences ("Create a new item successfully").
- `test.only` fails CI (`forbidOnly`).

## Before opening a PR
1. `uv run prek run --all-files` (lint, format, mypy, ty, typos, client regeneration)
2. `cd backend && uv run bash scripts/test.sh`
3. If UI changed: `bun run test`, then capture screenshots with `PR_SCREENSHOTS=1 bunx playwright test <spec>` and attach them to the PR (see `workflow.md`)
4. Full stack in Docker: `bash scripts/test.sh`
