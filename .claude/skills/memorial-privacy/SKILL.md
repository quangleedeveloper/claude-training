---
name: memorial-privacy
description: How Memorial Robot handles families' memories, media and personal data. Use when touching uploads, memory or extracted-memory models, endpoints that return memory data, logging and error messages, migrations on memory tables, AI clients, test data, or anything that stores what a family said.
---

Families give us their stories, photos, voices and videos of someone who has died.
Treat every byte as private to the family that uploaded it.

## Rules
1. **AI stays local.** Models run on Ollama and Whisper through the `LLMClient` and
   `Transcriber` protocols (`app/core/llm.py`, `app/services/transcription.py`).
   Never add a hosted LLM or speech API, and never send memory text or media off the
   machine. Tests use the fakes (`app/core/fake_ai.py`).
2. **Owner scoping on every read and write.** A user sees only their own memories,
   files and extracted items; superusers are the only exception, and only where the
   route says so. Every new endpoint gets a 403 test with a second normal user.
3. **No memory content in logs or errors.** Log IDs and counts, never story text,
   transcripts, extracted content, names from memories or file paths of uploads.
   `HTTPException` details stay generic; tests assert on them.
4. **Real uploads are off-limits to agents.** `backend/uploads/` holds real family
   media; a hook blocks reading it. Use synthetic data from `fixtures/` and the
   factories in `backend/tests/utils/`.
5. **Deletion really deletes.** Deleting a memory removes its files and extracted
   items (cascades plus files on disk). New tables that hold family data cascade from
   their owner and are covered by a delete test.
6. **Data-bearing migrations need a plan.** Never drop or rewrite a column holding
   memories without the backup step in the `how-we-write-migrations` skill.
7. **Synthetic only in fixtures and evals.** Invent families; never paste a real
   person's story, photo or recording into the repo.

## This skill is advisory
Hooks enforce rule 4 and the review pass in `REVIEW.md` rechecks rules 1–3 on every PR.
