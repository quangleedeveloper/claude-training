---
name: commit-message
description: Draft a Conventional Commit message for the staged changes, following .claude/rules/workflow.md. Use when the user asks for a commit message or asks to commit.
---

Draft a commit message for the current changes. Optional hint from the user: $ARGUMENTS

Steps:
1. Run `git status --short` and `git diff --cached --stat`.
   - If nothing is staged, show the unstaged and untracked files and ask which to stage. Don't stage anything on your own.
   - If you're on `main`, warn the user: `main` is protected (see `.claude/rules/workflow.md`). Suggest a branch named `<type>/<short-kebab-description>`.
2. Read the staged diff (`git diff --cached`). For large diffs, read the stat first, then the files that matter. Skip lock files and generated code (`uv.lock`, `bun.lock`, `frontend/src/client/`, `src/routeTree.gen.ts`).
3. Check that the commit is complete before drafting:
   - `backend/app/models.py` changed → an Alembic migration under `backend/app/alembic/versions/` should be staged too.
   - Backend API changed → the regenerated `frontend/src/client/` should be staged too.
   - New setting in `app/core/config.py` → `.env.example` should be updated too.
   - `.env` or anything that looks like a secret is staged → stop and tell the user.
   - The diff mixes unrelated changes → suggest splitting it into separate commits.
4. Write the message:

```
<type>: <imperative summary>

<body: what changed and why, wrapped at 72 chars; omit for trivial changes>

<footer: BREAKING CHANGE: ..., Refs #123 — only if relevant>
```

   - `type` is one of `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `build`. Pick it by the main intent of the change.
   - Summary line: 72 chars or fewer, lowercase, imperative mood ("add", not "added"), no trailing period. No scope in parentheses (the repo history doesn't use scopes).
   - The body explains *why*. The diff already shows *what*, so use bullets only when there are several distinct changes.
   - Mention migrations, new env vars and breaking API changes in the body.
5. Show the message in a code block, along with any warnings from step 3.
6. Commit only if the user asked to commit (in $ARGUMENTS or a reply). Then:
   - run `git commit -F -` with the message on stdin, so multi-line bodies keep their formatting
   - add the attribution trailer the session requires, if any
   - never use `--no-verify` or `--amend` unless the user asks
   - if the prek hooks rewrite files, re-stage those files and commit again
