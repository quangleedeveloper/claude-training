# Grounding evals

Cases that check the robot still answers only from the family's memories. They rerun
whenever the prompts (`backend/app/core/prompt.py`), the models, `CLAUDE.md`, the
skills or the hooks change. The runner and CI job come with the eval-suite ticket;
until then this folder holds the cases.

## One case per file: `evals/grounding/<id>.json`
```json
{
  "id": "G-001",
  "from": "AC-3.1",
  "fixture": "fixtures/families/<family>.json",
  "question": "What was Mom's first job?",
  "expect": {
    "fallback": false,
    "cites": ["<fixture item id>"],
    "must_include": ["<words the answer must contain>"],
    "must_not_include": ["<invented details>"]
  }
}
```
- `from`: the AC or incident the case protects. Every production incident adds one.
- `fallback: true` means the answer must be the fixed "no memory" reply and cite nothing.
- Fixtures are synthetic families only (see `fixtures/README.md`).
### Optional fields for persona cases (confirmed by the BA, MR-109 QA-1)
- `person`, `as`: the fixture person the conversation is with, and the fixture user asking (`owner` or `member`).
- `turns_before`: user messages sent earlier in the same open conversation.
- `summary`: a past-conversation summary loaded before the conversation opens.
- `expect.not_cites`: fixture item ids that must not be cited or in `sources`.
- `expect.fallback` left out: either outcome is fine; only the other checks apply.
- `note`: why the case may change (for example, a pending decision).

- Cases are protected: while `.claude/tests-locked` exists, a hook blocks edits here.
