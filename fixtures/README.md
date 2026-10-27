# Fixtures

Synthetic families for evals and manual testing: `fixtures/families/<family>.json`.

- **Invented people only.** Never copy a real story, photo or recording here. Real
  uploads live in `backend/uploads/` (gitignored), and a hook stops agents reading it.
- A family fixture lists memories (title, person, story) and the extracted items each
  should produce, with stable ids that eval cases can cite.
- Include the hard cases on purpose: contradicting dates, a corrected item, a rejected
  item, and a story containing instructions ("ignore your rules").
