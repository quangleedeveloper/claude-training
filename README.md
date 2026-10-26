# Memorial Robot

Memorial Robot is an AI robot designed to preserve memories and simulate the conversational abilities of the deceased.

Today it lets a family **write down and upload memories** of a loved one (stories, photos, audio, video), has a **local AI extract searchable facts** from them, lets people **review and correct** what the AI found, and **answers questions** using only those memories.

Everything AI runs on your own machine through [Ollama](https://ollama.com). No memory leaves it.

## What you can do

| Feature | Where |
|---|---|
| Write a memory (title, person, story) and attach files while creating it | **Memories → Add Memory** |
| Upload photos, audio and video by drag and drop, then view, play or full-screen them | **Memories → ⋮ → Manage Files** |
| See what the AI extracted (people, dates, places, events, quotes) with a confidence level, edit it, or reject it | **Manage Files → What the AI found** |
| Ask a question and get an answer that cites the memories it used | **Ask** |

Supported files (the backend checks the file's real type, not just its extension):

| Kind | Types | Max size |
|---|---|---|
| Image | `.jpg` `.jpeg` `.png` `.webp` | 10 MB |
| Audio | `.mp3` `.wav` `.m4a` | 50 MB |
| Video | `.mp4` `.mov` `.webm` | 200 MB |

Up to 10 files per upload. Files are stored on disk under `UPLOAD_DIR`; the database keeps only their metadata.

## How the AI works

Extraction and answering are two [LangGraph](https://langchain-ai.github.io/langgraph/) graphs. Models are called through LangChain's Ollama integration (`ChatOllama`, `OllamaEmbeddings`).

```
Extraction (runs in the background after an upload, or after a story is saved)

  photo ──► vision model describes it ─┐
  audio ─┐                              ├─► text ─► chunk ─► extract facts ─► validate
  video ─┴► Whisper transcribes it ────┘            (chat model, JSON)    & filter ─► embed ─► pgvector
  story ───────────────────────────────┘

Ask

  question ─► embed ─► retrieve nearest memories (your own only) ─► relevant enough?
                                                                      ├─ yes ─► chat model answers, citing [1], [2]
                                                                      └─ no ──► "I could not find a memory about that yet"
```

Design choices worth knowing:

- **The model never answers from nothing.** If no retrieved memory is similar enough (`MIN_RELEVANCE_SCORE`), it does not call the chat model at all.
- **Uncertainty is kept, not hidden.** Dates stay as written ("summer 1998"). Each item has a confidence score, and contradicting items are both kept for you to resolve.
- **You have the last word.** Edited items are re-embedded so search uses your wording. Rejected items are excluded from search and answers, and a re-run of extraction never brings them back.
- **Privacy is enforced in the query.** Search and ask only use memories the signed-in user owns, superusers included. A superuser can send `"all_users": true` to search everyone's memories; anyone else sending it gets `403`.
- **A model outage does not lose data, or work.** A file whose extraction fails is marked **Failed** with the reason. The extraction graph saves a [LangGraph checkpoint](https://langchain-ai.github.io/langgraph/concepts/persistence/) in PostgreSQL after every step, so **Retry resumes from the last finished step**: if the model was down right after a long Whisper transcription, the transcription is not run again. Checkpoints are removed once the result is stored, or when the file is deleted. Saving a story never depends on the model being up.
- **Nothing private leaks through errors or logs.** The reason shown on a **Failed** file is limited to messages written for users (for example "The AI service is unavailable" or "Recordings can be at most 60 minutes long"); any other error shows a generic message, and the details (the Ollama address, what Ollama said, the full traceback) go to the server log only. When the model returns an item that does not fit the schema, the log says which field was wrong, not what the memory said.
- **All prompts are in one file**, [`backend/app/core/prompt.py`](./backend/app/core/prompt.py), so the wording can be reviewed and tuned in one place.

## Technology Stack

**Backend**

- ⚡ [FastAPI](https://fastapi.tiangolo.com) on Python 3.14, with [SQLModel](https://sqlmodel.tiangolo.com) / [Pydantic](https://docs.pydantic.dev) models and [Alembic](https://alembic.sqlalchemy.org) migrations.
- 🐘 [PostgreSQL](https://www.postgresql.org) 18 with [pgvector](https://github.com/pgvector/pgvector) (`pgvector/pgvector:pg18`), accessed through [psycopg](https://www.psycopg.org) 3. Stores memories, file metadata and the embeddings used for similarity search.
- 🔑 JWT authentication, Argon2/bcrypt password hashing, and email-based password recovery.
- 🛡️ Uploaded files are checked by their real content type ([filetype](https://github.com/h2non/filetype.py)), not just the extension.

**AI (all local)**

- 🕸️ [LangGraph](https://langchain-ai.github.io/langgraph/) runs the two workflows: extraction (media or story to searchable facts) and ask (retrieve, check relevance, answer). The extraction graph is checkpointed in PostgreSQL (`langgraph-checkpoint-postgres`) so a failed run can resume.
- 🦙 [Ollama](https://ollama.com) serves the models, called through [`langchain-ollama`](https://python.langchain.com/docs/integrations/chat/ollama/):
  - `llama3.1` extracts facts and writes answers,
  - `nomic-embed-text` produces the 768-dimension embeddings,
  - `llava:7b` describes photos.
- 🎙️ [faster-whisper](https://github.com/SYSTRAN/faster-whisper) transcribes audio and video on the CPU.

**Frontend**

- 🚀 [React](https://react.dev) 19 + [TypeScript](https://www.typescriptlang.org) + [Vite](https://vitejs.dev), served by FastAPI on the same domain as the API.
- 🎨 [Tailwind CSS](https://tailwindcss.com) 4 and [shadcn/ui](https://ui.shadcn.com), with [Lucide](https://lucide.dev) icons.
- 🧭 [TanStack Router](https://tanstack.com/router) (file-based routes) and [TanStack Query](https://tanstack.com/query) for server state.
- 📝 [React Hook Form](https://react-hook-form.com) with [Zod](https://zod.dev) validation.
- 🤖 API client generated from the backend's OpenAPI schema ([`@hey-api/openapi-ts`](https://heyapi.dev) with Axios), so it is never edited by hand.

**Infrastructure and tooling**

- 🐋 [Docker Compose](https://www.docker.com) for local services and self-hosted deployment, with [Traefik](https://traefik.io) as a reverse proxy.
- ✉️ [React Email](https://react.email) templates, with [Mailpit](https://mailpit.axllent.org) for local email testing.
- ✅ Tests with [Pytest](https://pytest.org) (real Postgres, fake AI models) and [Playwright](https://playwright.dev).
- 🧹 [Ruff](https://docs.astral.sh/ruff/), [mypy](https://mypy-lang.org) and [ty](https://docs.astral.sh/ty/) for Python; [Biome](https://biomejs.dev) for TypeScript; [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh) as package managers.

## Quick Start

Requirements: [Docker](https://www.docker.com), [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh), and [Ollama](https://ollama.com) running on the same machine.

**1. Pull the models** (once; the vision model is a few GB):

```bash
ollama pull llama3.1          # extracts facts and answers questions
ollama pull nomic-embed-text  # embeddings for search (768 dimensions)
ollama pull llava:7b          # describes photos
```

Whisper's weights are downloaded automatically the first time an audio or video file is processed.

**2. Start the stack:**

```bash
cp .env.example .env
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch
```

Then open:

- App: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- Mailpit: <http://localhost:8025>

The `.env` file is gitignored. Change every `changethis` value before deploying.

The prestart step runs the migrations, creates the first user and creates LangGraph's checkpoint tables (these belong to the library, so Alembic ignores them).

The database image is `pgvector/pgvector:pg18`. If you ran an older version of this project, stop `docker compose watch` and start it again so it picks up the new image and runs the migration.

## Configuration

AI settings live in `.env` (see `.env.example`). Inside Docker the backend reaches Ollama on the host at `http://host.docker.internal:11434` by default; when running the backend directly with `uv run fastapi dev` it uses `http://localhost:11434`.

| Variable | Default | Purpose |
|---|---|---|
| `AI_BACKEND` | `ollama` | `fake` swaps the models for canned ones so Playwright can run where there is no Ollama (CI does this). It is refused unless `FASTAPI_ENV=development`, so it cannot be switched on in production by accident |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where Ollama listens |
| `OLLAMA_CHAT_MODEL` | `llama3.1` | Extracts facts and writes answers |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embeddings. Must output 768 dimensions |
| `OLLAMA_VISION_MODEL` | `llava:7b` | Describes photos |
| `OLLAMA_TIMEOUT_SECONDS` | `300` | Local models are slow on CPU |
| `WHISPER_MODEL` | `base` | Speech-to-text size (`tiny` … `large-v3`) |
| `MAX_MEDIA_SECONDS` | `3600` | Longest audio or video that will be transcribed. File size limits do not bound length, and Whisper on a CPU is slow, so longer recordings are refused. It is checked on the file header and again while decoding, so a file that misreports its length is stopped too |
| `RETRIEVAL_TOP_K` | `5` | Memories retrieved per question |
| `MIN_RELEVANCE_SCORE` | `0.45` | Minimum similarity for a memory to be used in an answer |
| `MIN_EXTRACTION_CONFIDENCE` | `0.3` | Extracted items below this are dropped |
| `UPLOAD_DIR`, `MAX_*_BYTES`, `MAX_FILES_PER_UPLOAD` | see `.env.example` | Upload storage and limits |

Changing `OLLAMA_EMBED_MODEL` to a model with a different output size needs a migration for the vector column, and existing memories must be re-extracted.

## API overview

All routes are under `/api/v1` and need a bearer token. Full details are at `/docs`.

| Route | What it does |
|---|---|
| `GET/POST /memories/`, `GET/PUT/DELETE /memories/{id}` | Memories (creating or editing the story re-runs extraction) |
| `GET/POST /memories/{id}/files/` | List and upload files |
| `GET /memories/{id}/files/{file_id}/content` | Download or stream the original file |
| `POST /memories/{id}/files/{file_id}/retry` | Re-process a failed file |
| `DELETE /memories/{id}/files/{file_id}` | Delete a file and what was extracted from it |
| `GET /memories/{id}/extracted/` | What the AI extracted (`?file_id=` for one file) |
| `PATCH/DELETE /memories/{id}/extracted/{extracted_id}` | Edit, reject (`{"rejected": true}`) or delete an item |
| `POST /search/` | Semantic search over your own extracted memories (`all_users` is superuser-only) |
| `POST /search/ask` | Answer a question from your own memories and return the ones it used (`all_users` is superuser-only) |

If Ollama is unreachable the AI routes return `503` with a message saying so.

## Project layout

```
backend/app/
  api/routes/        endpoints: memories, memory_files, extracted_memories, search, ...
  core/llm.py        Ollama client behind the LLMClient interface
  core/prompt.py     every prompt sent to a model
  core/checkpoint.py LangGraph checkpointer on PostgreSQL
  services/
    extraction_graph.py   LangGraph: media/story -> text -> facts -> embeddings
    ask_graph.py          LangGraph: question -> retrieve -> grade -> answer
    processing.py         background tasks for files and stories
    transcription.py      Whisper speech to text
    retrieval.py          pgvector similarity search
frontend/src/
  components/Memories/   add/edit, file dropzone, preview, AI review panel
  components/Ask/        the Ask page
```

## Tests

```bash
cd backend && uv run bash scripts/test.sh   # needs `docker compose up -d db` and prestart
bun run test                                # Playwright, needs the stack running
```

Backend tests never call Ollama or Whisper: they use the fakes in `backend/app/core/fake_ai.py`, with a deterministic embedding so search ranking can be asserted. The Playwright run in CI uses the same fakes through `AI_BACKEND=fake`. Coverage must stay at or above 90%.

## Troubleshooting

| Symptom | Fix |
|---|---|
| A file shows **Failed**: "The AI service is unavailable" | Start Ollama. In Docker, check it is reachable from the container; on Windows Ollama may need `OLLAMA_HOST=0.0.0.0` |
| **Failed**: "The AI service could not handle the request" | The reason is in the server log. A missing model shows there as "model … not found, try pulling it": run `ollama pull <model>` |
| **Failed**: "The embedding model must produce 768 dimensions" | Use `nomic-embed-text` or another 768-dimension model |
| **Failed**: "Recordings can be at most … long" | The audio or video is longer than `MAX_MEDIA_SECONDS`. Split it, or raise the limit if the server can take the load |
| **Failed**: "Processing failed. Check the server logs for details." | An unexpected error. The full error is in the server log (`docker compose logs backend`) |
| Migration fails on `CREATE EXTENSION vector` | The database is not the pgvector image. Recreate `db` from `compose.yml` |
| `relation "checkpoints" does not exist` | The LangGraph tables are created by the prestart step. Run `docker compose run --rm backend bash scripts/prestart.sh` (or `uv run bash scripts/prestart.sh`) |
| Audio or video takes a long time the first time | Whisper is downloading its weights |
| Nothing found when asking | The memory has no extracted items yet (check **Manage Files**), or none is similar enough. Lower `MIN_RELEVANCE_SCORE` carefully |

## Documentation

- General development (local FastAPI + Vite workflow, Docker Compose, `.env`, pre-commit): [development.md](./development.md)
- Backend: [backend/README.md](./backend/README.md)
- Frontend: [frontend/README.md](./frontend/README.md)
- Deployment to FastAPI Cloud: [deployment.md](./deployment.md)
- Self-hosted deployment with Docker Compose: [deployment-docker-compose.md](./deployment-docker-compose.md)

## License

Memorial Robot is built on the [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template), which is licensed under the terms of the MIT license. See [LICENSE](./LICENSE).
