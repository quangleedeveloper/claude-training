---
description: Draft a short stand-up update from my recent git activity
---

# Stand-up Update

Draft a stand-up update for me. Extra context or a time window from me: $ARGUMENTS

Steps (read-only; don't commit, stage or push anything):

1. Find my commits since yesterday morning, or in the window I gave:
   `git log --all --author="$(git config user.name)" --since="yesterday 00:00" --pretty=format:'%h %s (%D)'`
2. Run `git status --short` and `git branch --show-current` to see what is in progress.
3. Group the commits by branch and by topic. Skip merge commits and trivial chores unless nothing else happened.

Write the update in this format, at most 6 bullets in total:

**Yesterday**
- what I finished, in plain language and not as commit subjects

**Today**
- what the in-progress branch or uncommitted changes suggest I'm doing next

**Blockers**
- anything that looks stuck (failing hooks, unmerged dependent branches, an open question), or "None"

If there's no activity in the window, say so and ask me what to report instead of inventing work.
