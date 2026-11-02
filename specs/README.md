# Specs

One folder per feature: `specs/<feature>/spec.md`, written from an accepted
`intent/<feature>.md` with the `ba-intake` skill (`.claude/skills/ba-intake/templates/spec.md`).

- Requirements are numbered `FR-n` / `NFR-n`; acceptance criteria `AC-<fr>.<n>`.
  Tickets, tests, evals and reviews refer to these IDs, so never renumber them.
- Plans from plan mode go in `specs/<feature>/plans/MR-<n>.md`. If the build diverges,
  update the plan in the same commit.
- The client (the Lead) approves the spec. Pending questions stay in *Areas of concern*
  with the safe default the spec uses until they are decided.
