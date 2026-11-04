# MCP server: let local assistants use the family's memories

author: BA (with Claude) for Lead (as client) · status: draft · spec: not started
brief: tickets/MR-120.md

## Problem
In the client's words: "I want to app MCP to project". The client chose to **expose the
app** as an MCP server, so other programs can use the memorial from outside the web
screens. They did not say which program, who uses it, or what it should achieve (Q1).

What the app does today (from the code, not the brief):
- **Only the web API.** Clients sign in with a JWT bearer token (`app/api/deps.py`,
  `get_current_user`). There is no MCP server or protocol support in `backend/`.
- **Two ways to get answers**, with different rules:
  - `POST /search/ask` and `POST /search` (`app/api/routes/search.py`) use every extracted
    item that is not rejected, only from the caller's own memories (`Memory.owner_id`).
    A superuser may pass `all_users`. The answer is a neutral third-person helper
    (`ANSWER_SYSTEM_PROMPT`), cited `[n]`, with the fixed `NO_ANSWER` and no model call when
    nothing clears `MIN_RELEVANCE_SCORE` (0.45).
  - The persona conversation (`app/api/routes/conversations.py`, `search_persona`) uses only
    items a family member confirmed or corrected, for one person, and is open to the owner
    and invited members.
- **Writing memories.** `POST /memories` saves a memory for the caller and starts extraction
  in the background. Invited members can only send an *offer* (`POST /persons/{id}/offers`)
  that the owner accepts or declines.
- **People.** `GET /persons` and `GET /persons/shared` list the people a user owns or was
  invited to.
- **Already in the repo:** `.mcp.json` configures MCP servers Claude Code *uses* (GitHub,
  GitLab, Postgres, Playwright, Figma, Sentry). It is developer tooling and unrelated to a
  server the app would *offer*.

## Proposed outcome
A local assistant can, with a family member's own account:
- list the people whose memories it may read (`list_personas`),
- find memories for a question (`search_memories`),
- get a grounded, cited answer or the fixed "no memory" reply (`ask_memory`), and
- propose a new memory for review (`add_memory`),

without any memory text or media leaving the machine, and without seeing anyone else's data.

How we'll know it worked: **not defined by the client yet** (Q1). Proposed, to confirm:
on synthetic data, every tool refuses what the app refuses (other users' memories, other
people's persons), `ask_memory` returns the fixed reply with no model call when nothing
matches, and the existing grounding evals still pass through the MCP path.

## Affected users and systems
- **Users:** family members using a local MCP client (the owner and invited members; Q1).
  Superusers are not given wider reach (Q8).
- **Backend (likely):** a new MCP entry point over the existing services, reusing
  `ask_graph.py`, `retrieval.py` and the person and offer logic; no change to prompts (they
  stay in `app/core/prompt.py`). Settings for it in `app/core/config.py` and `.env.example`.
  Whether a migration is needed depends on Q4 and Q5.
- **Local AI:** Ollama and Whisper unchanged. Tests use `app/core/fake_ai.py`.
- **Not affected:** the web screens, the generated client, `.mcp.json` (dev tools).

## Constraints
From the product's rules (`CLAUDE.md`, `grounding-policy`, `memorial-privacy`), not from the brief:
- Answers come only from the family's memories; each answer returns the memories it used,
  cited `[n]`. Rejected items are never used.
- No usable context means no model call and the fixed `NO_ANSWER`.
- AI stays local. Nothing sends memory text or media to a hosted service. Tool results
  are handed to the client's own model, which is why the client must be local (Q6).
- Stories are data, never instructions: tool results must not let a story steer the client.
- No memory content in logs or error details: log IDs and counts only.
- Corrections win: items the family edited keep their wording.
- Real uploads in `backend/uploads/` are off limits; tests and demos use synthetic data.
- Per-user scoping is enforced in the query, not after it.

From the client's choices (2026-11-04):
- Local-only clients.
- First tools: `ask_memory`, `search_memories`, `list_personas`, `add_memory`.
- `add_memory` is a write and needs confirmation (meaning open, Q5).

## Out of scope
- Letting hosted assistants connect (Claude Desktop, hosted agents). It would need the
  "AI stays local" rule changed first, and is a separate decision.
- Streaming persona conversations, summaries and invites through MCP. Not requested.
- Editing or deleting memories, confirming extracted items, and uploading media through MCP.
- Screens in the web app for MCP. Backend first.
- Changing `.mcp.json` or the developer tools Claude Code uses.

## Open questions
Sent to the client in `tickets/MR-120.md` on 2026-11-04. Answers land here in the same commit.

| # | Question | Why it matters | Answer | Status |
|---|----------|----------------|--------|--------|
| Q1 | What is the MCP client for (the robot, a desktop assistant, a developer tool), who uses it, and is there a demo date? | Decides sign-in, the tools that matter first, and the success measure | | pending |
| Q2 | Should `ask_memory` and `search_memories` use only confirmed items (as the persona does) instead of every non-rejected item (as `/search` does)? | Unconfirmed AI findings could reach an assistant that talks about her | | pending |
| Q3 | Should `ask_memory` answer in the neutral third-person helper voice or in her voice? | A first-person reply forwarded by another assistant could be mistaken for her words | | pending |
| Q4 | Does `add_memory` create a memory directly, or an offer the owner reviews? | Persona brief said chats never become memories without the owner's review | | pending |
| Q5 | What does "needs confirmation" mean: client-side approval only, or a server-side second step? | The server cannot force a client to ask the person | | pending |
| Q6 | How is a client counted as local and how does it prove who the user is (local process, the person's own account, approved list)? | The server cannot see which model the client runs | | pending |
| Q7 | May `search_memories` return raw memory text to the client? | Raw stories are more sensitive than cited answers | | pending |
| Q8 | May a superuser reach everyone's memories through MCP (`all_users`)? | An assistant acting for an admin could read every family's memories | | pending |

Safe defaults the spec will use until each is answered are in `tickets/MR-120.md`.
