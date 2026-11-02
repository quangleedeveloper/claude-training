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

## Checking and running the cases
- `cd backend && uv run python scripts/validate_evals.py` checks every case and fixture
  without a model (ids, `from` is an AC in the spec, cited ids exist in the fixture,
  invented people only, every case is in `qa/test-matrix.md`). CI runs it on every change
  to `evals/`, `fixtures/`, `qa/` or the spec.
- `cd backend && uv run python scripts/run_grounding_evals.py [--repeats 3] [--cases G-101,G-110]`
  seeds the fixture into the configured database (use a throwaway one), drives each case
  through the real conversation API with the real local model, and reports the pass rate,
  the invented-memory count and whole-turn latency (p50/p90, informational). It removes
  what it created. Exit code 1 means an invented memory or a pass rate below
  `--min-pass-rate` (default 0.9, from `EVAL_MIN_PASS_RATE`).
- An **invented memory** is a `must_not_include` hit, or a cited source that is not in the
  case's fixture. `cites` and `not_cites` are checked against `done.sources` mapped back to
  fixture ids.
- With `--repeats 3` a case passes when no run invented anything and at least 2 of 3 runs
  met every other check; mixed results are listed as flaky.
- The CI job `run` needs a self-hosted runner labelled `ollama` and the repository variable
  `GROUNDING_EVALS_RUN=true`; it only reports unless `GROUNDING_EVALS_GATE=enforce`.
