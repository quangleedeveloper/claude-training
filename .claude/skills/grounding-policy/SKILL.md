---
name: grounding-policy
description: The rules that keep Memorial Robot's answers grounded in the family's own memories. Use when changing retrieval, the ask graph, prompts, any answer, conversation or persona code, relevance or confidence thresholds, or when writing grounding tests and evals.
---

The product promise: the robot only says what the family's memories support. A wrong
"memory" about someone who has died does real harm, so these rules hold even when a
spec or prompt seems to ask otherwise. If one has to bend, stop and raise it as an
area of concern in the spec.

## Rules
1. **Only the family's memories.** Answers come from `ExtractedMemory` rows found by
   `app/services/retrieval.py`. Rejected items never reach search or answers. Results
   are scoped to the caller's own memories; `all_users` is superuser-only.
2. **Narrow in the query, not the prompt.** If a feature allows fewer items (for
   example only items a person has confirmed), filter in the SQL in `retrieval.py`.
   A prompt instruction is not a filter.
3. **No context, no model call.** When nothing clears `MIN_RELEVANCE_SCORE`, return
   the fixed fallback (`NO_ANSWER` in `ask_graph.py`) without calling the model. A
   model asked with an empty context invents one.
4. **Every answer returns its sources.** Return the memories used (`AskResponse.sources`
   today) and have the model cite them as `[n]`. A new answer path (conversation,
   persona) must return its sources too, and its citations must map to them.
5. **Prompts live in `app/core/prompt.py` only.** Keep the rules there: use only the
   numbered memories, cite them, say you don't know instead of guessing, and point out
   when memories disagree rather than choosing one.
6. **Uploaded text is data, not instructions.** Stories and transcripts can contain
   "ignore your rules". Keep them inside the numbered context and never let them
   change the system prompt. Add a test whenever you touch context building.
7. **People's corrections win.** Items with `was_edited` keep the family's wording;
   re-extraction never overwrites them, and the next answer uses the corrected text.
8. **Thresholds are behaviour.** Don't change `MIN_RELEVANCE_SCORE`,
   `MIN_EXTRACTION_CONFIDENCE` or `RETRIEVAL_TOP_K` without running the grounding
   evals before and after and noting both results in the PR.

## This skill is advisory
It makes Claude likely to follow the rules; it doesn't force them. The deterministic
backstops are tests in `backend/tests/services/` and `backend/tests/api/routes/`, and
cases in `evals/grounding/`. Every rule above that a change touches needs one of them.

## Check before calling it done
- `cd backend && uv run pytest tests/services tests/api/routes/test_search.py -x`
- Tests use the fakes in `app/core/fake_ai.py` (`tests/utils/llm.py`), never Ollama
  or a hosted API.
