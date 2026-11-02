# Tickets

One Markdown file per ticket: `tickets/MR-<n>.md`
(template: `.claude/skills/ba-intake/templates/ticket.md`).

- The client's brief goes in its own ticket first, **verbatim**, before anyone asks a
  question. Open questions back to the client are posted in that ticket.
- Each delivery ticket lists the FR and AC IDs it covers from `specs/<feature>/spec.md`.

## The one rule
**Questions only in the ticket's `## Questions` section.** Not in chat, not in a call.
The BA answers there and updates `spec.md` in the same PR, so the spec stays the single
source of truth. A question asked anywhere else didn't happen.
