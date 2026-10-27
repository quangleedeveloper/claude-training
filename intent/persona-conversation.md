# Persona conversation: "make it feel like talking to Mom"

author: BA (with Claude) for Lead (as client) · status: draft
brief: tickets/MR-100.md

## Problem
In the client's words: families say asking the app "feels like searching a database".
They want it to feel like talking to the person they lost.

What the app does today (from the code, not the brief):
- `POST /search/ask` answers **one question at a time**. Nothing from earlier
  questions is kept, so it can't "remember what we talked about last time".
- Answers are written by a neutral helper *about* the person, in the third person
  (`ANSWER_SYSTEM_PROMPT` in `app/core/prompt.py`), with `[n]` citations to the memories used.
- Memories belong to the one user who wrote or uploaded them (`Memory.owner_id`).
  Other family members can't see or ask about them, so "the grandkids" can't use it today.
- The person is only a free-text `person_name` on each memory. There is no single
  record for "Mom" to attach a way of speaking to.
- Every extracted item that isn't rejected can be used in answers; nothing marks an
  item as confirmed by the family.

## Proposed outcome
Family members can hold a conversation with a persona of the person who died that:
- replies in the way that person spoke,
- uses only what the family's memories support, and
- recalls what that family member talked about with it before.

How we'll know it worked: *not yet defined* (Q11).

## Affected users and systems
- **Users:** the family member who builds the memorial today; other family members,
  including grandchildren (Q3, Q4).
- **Backend:** `app/services/ask_graph.py` and `retrieval.py` (grounding),
  `app/core/prompt.py` (persona voice), `app/models.py` (new person, conversation and
  access data, so migrations), `app/api/routes/search.py` or a new conversation route.
- **Possible sources of "the way she talked":** written stories, Whisper transcripts of
  audio and video, and extracted items with category `quote` (Q1, Q2).
- **Local AI:** Ollama chat model (`llama3.1`) and Whisper, currently slow on CPU (Q10).

## Constraints
These come from the product's existing rules (`CLAUDE.md`, the `grounding-policy` and
`memorial-privacy` skills), not from the brief:
- Only the family's own memories. Never invent a memory, a quote or a feeling.
- When the memories don't cover something, no model call on an empty context.
- AI stays local (Ollama, Whisper). No hosted AI service, no memory text or media off the machine.
- No memory content in logs or error messages.
- The family's corrections win over what the AI extracted.

## Out of scope
- App screens and the robot itself for this round: backend first (training scope).
- Anything else is undecided until the open questions are answered.

## Open questions
| # | Question | Why it matters | Answer | Status |
|---|----------|----------------|--------|--------|
| Q1 | Should the persona match her **written style** only, or also **sound like her** (her voice)? | Voice cloning is a separate system with its own consent and misuse risks | | pending |
| Q2 | Who is "Mom" in the data? Today the person is a free-text name on each memory. Is a persona one named person per memorial, and who decides that "Mom" and "Mẹ" are the same person? | Decides whether we need a new person record before anything else | | pending |
| Q3 | Who may talk with the persona: only the person who built the memorial, or family members they invite? Who can revoke that? | Today memories are private to one user; sharing is new access control | | pending |
| Q4 | Can grandchildren under 18 use it, and with whose consent? | Safety and consent rules for minors | | pending |
| Q5 | What should it say when the memories don't cover a question? | Grounding: the alternative to a fixed reply is the model inventing an answer | | pending |
| Q6 | What does "remember what we talked about last time" keep: the full chat or a summary, per family member or shared, for how long, and can it be deleted? Do things said in a chat ever become memories? | Data model, privacy, deletion, and whether chats can change the record of her life | | pending |
| Q7 | Does the persona ever speak as her in the first person ("I remember…") or claim to be her? Is it always clear it's an AI recreation? | Honesty with grieving families | | pending |
| Q8 | Should it use every extracted item that isn't rejected (as search does today), or only items a family member has confirmed? | There is no "confirmed" state today, so this adds a review step and changes what it knows | | pending |
| Q9 | When is "the next demo", and what has to be shown there: a working API, or a clickable conversation? | Scope and slicing; frontend is out of scope this round | | pending |
| Q10 | How fast must a reply feel? The local model is slow on CPU (the app allows each call up to 300 s). | Decides streaming, model size and hardware, without moving to a hosted AI | | pending |
| Q11 | How will families judge that it "feels like talking to Mom"? | We need a measurable outcome before we can test it | | pending |
