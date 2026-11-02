# QA

`qa/test-matrix.md` holds one section per feature
(template: `.claude/skills/ba-intake/templates/test-matrix.md`), drafted by QA from the
acceptance criteria in `specs/<feature>/spec.md`.

- At least one row per AC, including negative, security and compliance cases.
- Each row names the test (`backend/tests/...`) or eval case (`evals/grounding/...`)
  that proves it. Write the rows before the code, so devs have measurable targets.
- An AC you can't test is a question: ask it in the ticket, don't rewrite the AC.
