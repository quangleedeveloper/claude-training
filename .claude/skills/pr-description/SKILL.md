---
name: pr-description
description: Writes pull request descriptions. Use when creating a PR, writing a PR, or when the user asks to summarize changes for a pull request.
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git status:*)
model: sonnet
---

When writing a PR description:

1. Run `git diff main...HEAD` to see all changes on this branch
2. Write a description following this format:

## What
One sentence explaining what this PR does.

## Why
Brief context on why this change is needed

## Changes
- Bullet points of specific changes made
- Group related changes together
- Mention any files deleted or renamed

## How it was tested
- The commands that were run and what passed. Say plainly what could not be run.

## Screenshots
- If `git diff main...HEAD --stat` touches `frontend/src/`, the description needs screenshots of the screens changed: the main state, an empty or error state, and before/after for a changed screen. You cannot upload images yourself, so list each screen that needs one and say where to get it (`PR_SCREENSHOTS=1 bunx playwright test <spec>` writes full-page PNG files to `frontend/test-results/`; the PR's Playwright run also uploads `pr-screenshots-*` artifacts). Never use real family data.
- Otherwise write "No UI change".

## Migrations and env vars
- A new Alembic migration, new `Settings` or `.env.example` entries, or "None".
