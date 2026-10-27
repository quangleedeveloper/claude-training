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
- Cases are protected: while `.claude/tests-locked` exists, a hook blocks edits here.
