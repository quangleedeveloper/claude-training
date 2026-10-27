# Review policy

Claude reviews every PR in these passes and tags each finding with its pass. Findings
inform the code owner; they never approve or block a PR on their own. The agent that
wrote a change never approves it.

## Passes
1. **Bugs**: logic errors, edge cases, regressions, missing migrations for `models.py`
   changes, a stale generated client.
2. **Privacy and security** (`memorial-privacy` skill): no hosted AI or calls off the
   local runtime; no memory text, transcripts or upload paths in logs or error details;
   no secrets; injection and auth gaps.
3. **Access**: every endpoint that returns family data is scoped to its owner, with a
   403 test using a second normal user; `all_users` stays superuser-only.
4. **Grounding** (`grounding-policy` skill): answers only from non-rejected, owned
   memories; no model call on an empty context; sources returned and cited; prompts only
   in `app/core/prompt.py`; threshold changes come with eval results.
5. **Compliance**: the change matches its ticket's FR and AC IDs in
   `specs/<feature>/spec.md` and its plan in `specs/<feature>/plans/`; tests or eval
   cases exist for each AC it claims; questions were answered in the ticket, not elsewhere.

## Severity
- **Important**: breaks behaviour, leaks family data, lets the robot invent or misattribute
  a memory, or breaches a rule above.
- **Nit**: style, naming, small readability points. At most 5 per review; summarize the
  rest as a count.

## Don't report
- `frontend/src/client/`, `frontend/src/routeTree.gen.ts`, `backend/app/email-templates/build/`,
  `uv.lock`, `bun.lock`
- Anything ruff, Biome, mypy, ty or the coverage gate already enforce

## Feeding back
A mistake flagged a second time goes into `CLAUDE.md` in the same review.
