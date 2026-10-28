# Persona conversation: "make it feel like talking to Mom"

author: BA (with Claude) for Lead (as client) · status: ready for Lead review
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

How we'll know it worked (Q11): two family members who knew her rate 20 replies on
synthetic data, blind; “sounds like her” and “true to her memories” average 4 or more
out of 5, with zero invented memories. After launch, we track “not how she talked” flags.

## Affected users and systems
- **Users:** the family member who builds the memorial (owner of the person record);
  family members the owner invites, who can only talk with the persona (Q3);
  adults only in v1 (Q4); grandchildren in a separate brief later.
- **Backend:** `app/services/ask_graph.py` and `retrieval.py` (grounding),
  `app/core/prompt.py` (persona voice), `app/models.py` (a new person record linked to
  memories (Q2), plus conversation and access data, so migrations), `app/api/routes/search.py` or a new conversation route.
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

From the client's answers:
- Uses only items a family member confirmed or corrected; adds a confirm step (Q8).
- When nothing matches: a fixed reply that there is no memory of that, no citations (Q5).
- May speak in the first person, never claims to be her; every conversation opens with
  an AI-recreation notice (Q7).
- Remembers through a per-member summary only that member sees; deletable; deleted on
  revoke; chats never become memories without the owner's review (Q6).
- First words within about 3 s (streaming), full reply within about 30 s, still local (Q10).
- Next demo 2026-11-11, date to confirm: backend API on synthetic data only (Q9).

## Out of scope
- App screens and the robot itself for this round: backend first (training scope).
- Sounding like her (voice cloning or voice output): a separate brief later (Q1).
- Users under 18: a separate brief later, designed with guardian consent and privacy-law review (Q4).

## Open questions
Sent to the client in `tickets/MR-100.md` on 2026-10-27. Answers land here in the same commit. All answered 2026-10-28.

| # | Question | Why it matters | Answer | Status |
|---|----------|----------------|--------|--------|
| Q1 | Should the persona match her **written style** only, or also **sound like her** (her voice)? | Voice cloning is a separate system with its own consent and misuse risks | Words now, voice later: match her phrasing, nicknames and tone from stories, transcripts and quotes; her voice is a separate brief later, with its own consent rules | answered |
| Q2 | Who is "Mom" in the data? Today the person is a free-text name on each memory. Is a persona one named person per memorial, and who decides that "Mom" and "Mẹ" are the same person? | Decides whether we need a new person record before anything else | A person record: one per person remembered, one persona per record. The memorial builder links memories to it and decides which names are the same person; the AI may suggest a match, a person confirms | answered |
| Q3 | Who may talk with the persona: only the person who built the memorial, or family members they invite? Who can revoke that? | Today memories are private to one user; sharing is new access control | Invited members: the builder owns the person record and invites others; invitees can talk with the persona but not edit memories or invite; only the owner revokes, which ends that member's open chats | answered |
| Q4 | Can grandchildren under 18 use it, and with whose consent? | Safety and consent rules for minors | Adults only in v1: only members 18+ can be invited; children are a separate brief later, with guardian consent and a privacy-law check | answered |
| Q5 | What should it say when the memories don't cover a question? | Grounding: the alternative to a fixed reply is the model inventing an answer | A fixed, gentle reply: no memory of that, invites the member to add the story; cites nothing; no model call when nothing matches | answered |
| Q6 | What does "remember what we talked about last time" keep: the full chat or a summary, per family member or shared, for how long, and can it be deleted? Do things said in a chat ever become memories? | Data model, privacy, deletion, and whether chats can change the record of her life | A summary per member, private to them; kept until they delete it, deleted when access is revoked; chats never become memories on their own, a member may offer one for the owner to review | answered |
| Q7 | Does the persona ever speak as her in the first person ("I remember…") or claim to be her? Is it always clear it's an AI recreation? | Honesty with grieving families | May speak in the first person in her way, never claims to be her; every conversation opens with an AI-recreation notice; answers plainly if asked | answered |
| Q8 | Should it use every extracted item that isn't rejected (as search does today), or only items a family member has confirmed? | There is no "confirmed" state today, so this adds a review step and changes what it knows | Only items a family member confirmed or corrected; unchecked AI findings are not used; adds a confirm step, search unchanged | answered |
| Q9 | When is "the next demo", and what has to be shown there: a working API, or a clickable conversation? | Scope and slicing; frontend is out of scope this round | Demo 2026-11-11 (date to confirm): backend API only; open a conversation, show a grounded reply with sources, a “no memory” reply, and recall across conversations, on synthetic data | answered |
| Q10 | How fast must a reply feel? The local model is slow on CPU (the app allows each call up to 300 s). | Decides streaming, model size and hardware, without moving to a hosted AI | First words within ~3 s (streaming), full reply within ~30 s on the demo machine; if CPU can't, smaller local model or local GPU, never hosted AI | answered |
| Q11 | How will families judge that it "feels like talking to Mom"? | We need a measurable outcome before we can test it | Blind rating of 20 replies by two family members who knew her: “sounds like her” and “true to her memories” average 4+/5, zero invented memories; after launch, count “not how she talked” flags | answered |
