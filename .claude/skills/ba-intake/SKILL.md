---
name: ba-intake
description: Turn a rough client brief into the team's delivery artifacts (intent.md, open questions, spec.md, ticket pack, test matrix) using the templates in this skill. Use when someone pastes a brief, asks for intake, or asks to draft or update an intent, spec, tickets or test matrix.
---

Request from the user, if any: $ARGUMENTS

Each step ends with a file committed to the repo; the next step starts by reading it.
Templates are in `templates/` next to this file. Copy them; don't invent new layouts.

## 1. Record the brief (`tickets/MR-<n>.md`)
- Paste the client's words **verbatim** into a new ticket before asking anything. Never tidy them up: the original wording is the evidence of what was asked.

## 2. Intake → `intent/<feature>.md` (template: `templates/intent.md`)
- Ask analyst questions until the brief is concrete: who is affected, what they can't do today, what better looks like, what is out of scope, how success is measured.
- **Never fill a gap with a guess.** Anything the brief doesn't say goes into *Open questions*, with why it matters.
- Describe today's behaviour from the code, not from the brief (read `backend/app/models.py`, `app/services/`, `app/api/routes/`). If the brief assumes something the code doesn't have, say so as an open question.
- Status starts as `draft`. The client (the Lead in training) corrects it; the merge means `accepted`.

## 3. Open questions back to the client
- Post them as one comment in the brief's ticket, numbered Q1, Q2… Each answer updates the intent's *Open questions* table **in the same commit**. Unanswered ones stay `pending`.

## 4. Spec → `specs/<feature>/spec.md` (template: `templates/spec.md`)
- Start only from an accepted intent. Apply the `grounding-policy` and `memorial-privacy` skills.
- Number requirements `FR-1…` and non-functional ones `NFR-1…`. Give each FR acceptance criteria `AC-<fr>.<n>` in Given/When/Then form.
- *Areas of concern*: every pending question and every policy conflict, with the safe default the spec uses until it is decided, and who decides.

## 5. Ticket pack → `tickets/MR-<n>.md` (template: `templates/ticket.md`)
- One ticket per shippable slice, each listing its FR and AC IDs, size (S/M/L) and dependencies. Aim for slices that touch different files so they can run in parallel worktrees.
- Every ticket ends with a `## Questions` section. **Devs and QA ask only there**; the BA answers there and updates `spec.md` in the same PR.

## 6. Test matrix → `qa/test-matrix.md` (template: `templates/test-matrix.md`)
- One row per AC at least. Cover negative and security cases, not only the happy path.
- Rows whose level includes `eval` also get a case in `evals/grounding/` (see its README).

## Done when
- Every FR has ACs, every AC has a matrix row, every ticket links its FRs, and no question was answered outside a ticket.
