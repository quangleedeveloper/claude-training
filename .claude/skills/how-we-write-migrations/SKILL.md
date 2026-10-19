---
name: how-we-write-migrations
description: How we write, review and ship Alembic migrations for the backend. Use when models.py changes, when the user asks to create, edit or review a migration, or when a migration fails to apply.
---

Alembic migrations live in `backend/app/alembic/versions/`. Request from the user, if any: $ARGUMENTS

## Creating one
1. Change `backend/app/models.py` first (table classes, following the `XBase` → `X(table=True)` split).
2. Make sure the DB is up and at head: `docker compose up -d db`, then from `backend/`: `uv run alembic upgrade head`.
3. Generate: `uv run alembic revision --autogenerate -m "<imperative message>"`. Use the same style as the existing files, e.g. `add created_at to user and item`.
4. Never write the revision id or `down_revision` by hand. If two branches each add a revision, run `uv run alembic heads`, and resolve it with `uv run alembic merge heads -m "merge heads"`.

## Review the generated file (autogenerate is a draft, not the answer)
- Remove noise: unrelated `alter_column` or `drop_*` calls that autogenerate invented, and the `# ### commands auto generated ###` banners.
- Check that `upgrade()` matches the model change and nothing else. Check that `downgrade()` really reverses it, in reverse order.
- New `NOT NULL` column on a table that already has rows: add it as nullable, or with a `server_default`, backfill, and only then tighten it. A plain `nullable=False` fails on a non-empty table.
- Renames: autogenerate sees a drop plus an add, which loses data. Hand-write `op.alter_column(..., new_column_name=...)` or `op.rename_table`.
- Foreign keys: set `ondelete` explicitly (see `1a31ce608336_add_cascade_delete_relationships.py`). Name constraints and indexes explicitly when you create them by hand.
- Data migrations (backfills) use `op.execute(sa.text(...))` with SQL or lightweight `sa.table(...)` objects. Never import `app.models` inside a migration, because the models change later and the migration would break.
- Personal and memorial data (memories, conversations of the deceased): never drop or rewrite a column holding it without a backup step agreed with the team. Make the downgrade lossless, or say plainly in the PR that it isn't.

## Verify before committing
1. `uv run alembic upgrade head`, then `uv run alembic downgrade -1`, then `uv run alembic upgrade head` again. All three must succeed.
2. `uv run alembic check` reports no pending model changes.
3. `uv run bash scripts/test.sh` still passes (tests run against the real Postgres DB).

## Ship it
- Commit the migration in the same commit as the `models.py` change that produced it, together with the regenerated `frontend/src/client/` (`bun run --filter frontend generate-client`).
- Mention the migration in the PR description, with whether it is reversible and whether it touches existing rows.
- Never edit a migration that has been merged to `main`. Add a new one.
