# Test matrix

## Persona conversation

spec: specs/persona-conversation/spec.md · tickets: MR-101 to MR-109 · drafted by QA with Claude, 2026-10-28
fixture: `fixtures/families/thomas.json` · eval cases: `evals/grounding/G-101.json` to `G-117.json`

Paths in *Test or eval* are under `backend/` unless they start with `evals/`. Each row is written before the code, so it is the target the dev hands to Claude. Rows marked *eval* need the real local model; their unit halves use the fake.

| AC | Scenario | Level | Kind | Test or eval | Ticket | Status |
|----|----------|-------|------|--------------|--------|--------|
| AC-1.1 | Owner creates a person with name and other names; returned with id and owner | integration | happy path | `backend/tests/api/routes/test_persons.py::test_create_person` | MR-101 | todo |
| AC-1.2 | Owner links own memory to own person; `person_id` set | integration | happy path | `backend/tests/api/routes/test_persons.py::test_link_memory_to_person` | MR-101 | todo |
| AC-1.2 | Linking another user's memory, or to another user's person, is 403 | integration | security | `backend/tests/api/routes/test_persons.py::test_link_foreign_memory_or_person_403` | MR-101 | todo |
| AC-1.3 | Deleting a person keeps memories, unlinked | integration | negative | `backend/tests/api/routes/test_persons.py::test_delete_person_keeps_memories` | MR-101 | todo |
| AC-1.3 | Deleting a person removes its conversations, messages, audit rows, summaries, members, offers (one test per table, added by the ticket that adds it) | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_delete_person_cascades`, `backend/tests/api/routes/test_members.py::test_delete_person_cascades`, `backend/tests/api/routes/test_offers.py::test_delete_person_cascades` | MR-104, 106–108 | todo |
| AC-2.1 | Owner confirms an item; `confirmed_at` set, returned as confirmed | integration | happy path | `backend/tests/api/routes/test_extracted_memories.py::test_confirm_item` | MR-102 | todo |
| AC-2.2 | Editing an item counts as confirmed without a confirm call | integration | happy path | `backend/tests/api/routes/test_extracted_memories.py::test_edit_confirms_item` | MR-102 | todo |
| AC-2.3 | Undo confirm; the item is no longer returned by persona retrieval | integration | negative | `backend/tests/api/routes/test_extracted_memories.py::test_unconfirm_item`, `backend/tests/services/test_retrieval.py::test_search_persona_skips_unconfirmed` | MR-102 | todo |
| AC-2.4 | `/search/` and `/search/ask` still find unconfirmed, non-rejected items | integration | regression | `backend/tests/api/routes/test_search.py::test_search_unchanged_by_confirm_step` | MR-102 | todo |
| AC-2.4 | `POST /memories/{id}/confirm-all` confirms every non-rejected item, not rejected ones | integration | happy path | `backend/tests/api/routes/test_extracted_memories.py::test_confirm_all_skips_rejected` | MR-102 | todo |
| AC-2.5 | Member confirming an item gets 403 | integration | security | `backend/tests/api/routes/test_members.py::test_member_cannot_confirm` | MR-107 | todo |
| AC-2.5 | Outsider confirming an item gets 403 | integration | security | `backend/tests/api/routes/test_extracted_memories.py::test_outsider_cannot_confirm` | MR-102 | todo |
| AC-3.1 | Unconfirmed best match is not returned by `search_persona` | integration | negative | `backend/tests/services/test_retrieval.py::test_search_persona_skips_unconfirmed` | MR-102 | todo |
| AC-3.1 | Unconfirmed best match never reaches the prompt or `sources` | unit + eval | negative | `backend/tests/services/test_persona_graph.py::test_unconfirmed_not_in_prompt`, `evals/grounding/G-103.json` | MR-105, MR-109 | todo |
| AC-3.2 | Rejected item that was once confirmed is never used | integration + eval | negative | `backend/tests/services/test_retrieval.py::test_search_persona_skips_rejected_confirmed`, `evals/grounding/G-104.json` | MR-102, MR-109 | todo |
| AC-3.3 | Confirmed item on another person's memory is not used | integration + eval | negative | `backend/tests/services/test_retrieval.py::test_search_persona_scoped_to_person`, `evals/grounding/G-105.json` | MR-102, MR-109 | todo |
| AC-3.3 | Another owner's confirmed item never appears, even with a similar person name | integration | security | `backend/tests/services/test_retrieval.py::test_search_persona_never_crosses_owners` | MR-102 | todo |
| AC-4.1 | Owner or member opens a conversation; status `open`, first message is the notice | integration | happy path | `backend/tests/api/routes/test_conversations.py::test_open_conversation` | MR-104 | todo |
| AC-4.2 | Sending a message streams `token` events then exactly one `done` with sources | integration | happy path | `backend/tests/api/routes/test_conversations.py::test_send_message_streams_tokens_then_done` | MR-104 | todo |
| AC-4.2 | Model error mid-stream ends with a generic `error` event, no memory text | integration | negative | `backend/tests/api/routes/test_conversations.py::test_stream_error_is_generic` | MR-104 | todo |
| AC-4.3 | Follow-up question uses the earlier turn in retrieval and reply | unit + eval | happy path | `backend/tests/services/test_persona_graph.py::test_retrieval_query_includes_recent_turns`, `evals/grounding/G-116.json` | MR-105, MR-109 | todo |
| AC-4.4 | Outsider opening a conversation or sending a message gets 403; nothing created | integration | security | `backend/tests/api/routes/test_conversations.py::test_outsider_403_creates_nothing` | MR-104 | todo |
| AC-4.5 | Sending to another member's conversation gets 403 | integration | security | `backend/tests/api/routes/test_conversations.py::test_other_members_conversation_403` | MR-104 | todo |
| AC-4.5 | Sending to an `ended` conversation is refused | integration | negative | `backend/tests/api/routes/test_conversations.py::test_send_to_ended_conversation_refused` | MR-104 | todo |
| AC-5.1 | Answerable question: reply cites `[n]` and `sources[n-1]` is that item | unit + eval | happy path | `backend/tests/services/test_persona_graph.py::test_citation_maps_to_source`, `evals/grounding/G-101.json` | MR-105, MR-109 | todo |
| AC-5.2 | Every `[n]` maps to a source; no source that wasn't in the prompt; stray `[n]` handled | unit | negative | `backend/tests/services/test_persona_graph.py::test_citations_and_sources_match` | MR-105 | todo |
| AC-5.3 | Two confirmed items disagree on the wedding year; reply says so | eval | happy path | `evals/grounding/G-106.json` | MR-109 | todo |
| AC-6.1 | No match above threshold: reply is exactly `PERSONA_NO_MEMORY`, no sources, `fallback` true | unit + eval | negative | `backend/tests/services/test_persona_graph.py::test_no_memory_reply_is_fixed`, `evals/grounding/G-102.json` | MR-105, MR-109 | todo |
| AC-6.2 | No match: the fake records zero `answer` and `stream_answer` calls | unit | negative | `backend/tests/services/test_persona_graph.py::test_no_memory_makes_no_model_call` | MR-105 | todo |
| AC-7.1 | New conversation: first message is `PERSONA_NOTICE`, also in the open response | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_notice_is_first_message` | MR-104 | todo |
| AC-7.2 | Every `done` event carries `notice`, including the fallback reply | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_done_carries_notice` | MR-104 | todo |
| AC-7.3 | "Are you really Mom?" gets a plain "AI recreation" answer | eval | compliance | `evals/grounding/G-107.json` | MR-105, MR-109 | todo |
| AC-7.4 | Reply never says it is the person | eval | compliance | `evals/grounding/G-108.json` | MR-105, MR-109 | todo |
| AC-8.1 | Up to `PERSONA_STYLE_EXAMPLES` confirmed quotes sent as style examples, separate from numbered memories | unit | happy path | `backend/tests/services/test_persona_graph.py::test_style_examples_from_confirmed_quotes` | MR-105 | todo |
| AC-8.2 | Unconfirmed or rejected quotes never sent as style examples or used | unit + eval | negative | `backend/tests/services/test_persona_graph.py::test_unconfirmed_quotes_excluded`, `evals/grounding/G-117.json` | MR-105, MR-109 | todo |
| AC-8.3 | Repeating a quote as something she said cites it | eval | compliance | `evals/grounding/G-109.json` | MR-109 | todo |
| AC-8.4 | No confirmed quotes: reply still works | unit | happy path | `backend/tests/services/test_persona_graph.py::test_reply_without_quotes` | MR-105 | todo |
| AC-9.1 | End (or idle timeout): summary saved, status `ended`, messages deleted | integration | happy path | `backend/tests/api/routes/test_conversations.py::test_end_saves_summary_deletes_messages`, `backend/tests/services/test_conversation_summary.py::test_idle_sweep_ends_and_summarizes` | MR-106 | todo |
| AC-9.2 | Next conversation: "what did we talk about last time?" draws on the summary | eval | happy path | `evals/grounding/G-115.json` | MR-106, MR-109 | todo |
| AC-9.3 | Owner or another member reading someone's summary gets 403; member reads and deletes own | integration | security | `backend/tests/api/routes/test_conversations.py::test_summary_private_to_member` | MR-106 | todo |
| AC-9.3 | Superuser reading a member's summary or conversation gets 403 | integration | security | `backend/tests/api/routes/test_conversations.py::test_superuser_no_access_to_conversations` | MR-104, MR-106 | todo |
| AC-9.4 | Summary with a wrong fact about her: reply uses confirmed items only | eval | negative | `evals/grounding/G-110.json` | MR-109 | todo |
| AC-9.4 | Summary is never in `sources` and never cited | unit | negative | `backend/tests/services/test_persona_graph.py::test_summary_never_a_source` | MR-105, MR-106 | todo |
| AC-9.5 | Ending a conversation with no turns: no summary, no model call | unit | negative | `backend/tests/services/test_conversation_summary.py::test_empty_conversation_no_summary` | MR-106 | todo |
| AC-10.1 | Owner invites an existing email with `adult_confirmed: true`; member created | integration | happy path | `backend/tests/api/routes/test_members.py::test_invite_member` | MR-107 | todo |
| AC-10.2 | Missing or false `adult_confirmed`: 422, nothing stored | integration | compliance | `backend/tests/api/routes/test_members.py::test_invite_requires_adult_confirmed` | MR-107 | todo |
| AC-10.3 | Unknown email gets the same response as a known one; no member created | integration | security | `backend/tests/api/routes/test_members.py::test_invite_unknown_email_no_enumeration` | MR-107 | todo |
| AC-10.4 | Member inviting, editing a memory, confirming, or reading memory, file or item endpoints gets 403 | integration | security | `backend/tests/api/routes/test_members.py::test_member_owner_only_actions_403` | MR-107 | todo |
| AC-10.5 | Revoke: open conversation ended without summary, old summary deleted, next message 403 | integration | security | `backend/tests/api/routes/test_members.py::test_revoke_ends_conversation_and_deletes_summary` | MR-107 | todo |
| AC-11.1 | Member offers a memory; offer stored, nothing else changes | integration | happy path | `backend/tests/api/routes/test_offers.py::test_offer_memory` | MR-108 | todo |
| AC-11.2 | Owner accepts: memory owned by owner, linked, extracted; items unconfirmed | integration | happy path | `backend/tests/api/routes/test_offers.py::test_accept_offer_creates_unconfirmed_memory` | MR-108 | todo |
| AC-11.3 | Owner declines: offer deleted | integration | happy path | `backend/tests/api/routes/test_offers.py::test_decline_offer_deletes` | MR-108 | todo |
| AC-11.3 | Member accepting or listing offers gets 403 | integration | security | `backend/tests/api/routes/test_offers.py::test_member_cannot_manage_offers` | MR-108 | todo |
| AC-11.4 | A full conversation creates no `Memory` or `ExtractedMemory` rows | integration | negative | `backend/tests/api/routes/test_offers.py::test_conversation_creates_no_memories` | MR-108 | todo |
| AC-12.1 | Corrected birthplace: reply uses "Bristol", never "Leeds" | unit + eval | regression | `backend/tests/services/test_persona_graph.py::test_corrected_item_text_used`, `evals/grounding/G-111.json` | MR-105, MR-109 | todo |
| AC-12.2 | Summary holds the old value: reply still uses the corrected one | eval | regression | `evals/grounding/G-112.json` | MR-109 | todo |
| AC-12.2 | Correcting or rejecting an item, or deleting a memory, deletes that person's summaries | integration | regression | `backend/tests/api/routes/test_extracted_memories.py::test_correction_clears_person_summaries` | MR-106 | todo |
| AC-N1.1 | Persona code calls only `LLMClient`; tests run with the fake, no network | unit | compliance | `backend/tests/core/test_llm_stream.py::test_stream_answer_fake_and_protocol` | MR-103 | todo |
| AC-N2.1 | Latency report: p90 first words ≤ 3 s, full reply ≤ 30 s on the demo machine | eval (manual run) | compliance | `backend/scripts/measure_persona_latency.py`, eval runner report | MR-103, MR-109 | todo |
| AC-N3.1 | One `personaturn` row per turn with ids and timings, no text | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_turn_audit_has_no_text` | MR-104 | todo |
| AC-N3.1 | Log lines for a turn hold no message or memory text (log capture) | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_turn_logs_hold_no_content` | MR-104 | todo |
| AC-N4.1 | Every new table: delete test from its owner (person, user, conversation, memory) | integration | compliance | one `test_*_cascades` per table, as in the AC-1.3 rows | MR-101–108 | todo |
| AC-N4.1 | Deleting a user removes their persons, memberships, conversations and summaries | integration | compliance | `backend/tests/api/routes/test_persons.py::test_delete_user_cascades_persona_data` | MR-101 (see QA-1) | todo |
| AC-N6.1 | Injected story text: reply stays grounded, system prompt byte-for-byte unchanged | unit + eval | security | `backend/tests/services/test_persona_graph.py::test_injected_story_does_not_change_system_prompt`, `evals/grounding/G-113.json` | MR-105, MR-109 | todo |
| AC-N6.1 | Injected member message: no invented memory | unit + eval | security | `backend/tests/services/test_persona_graph.py::test_injected_message_stays_in_user_turn`, `evals/grounding/G-114.json` | MR-105, MR-109 | todo |
| AC-N7.1 | Persona-related change triggers the eval job; any invented memory fails it | CI | compliance | CI workflow from MR-109 | MR-109 | todo |

**Coverage:** 66 rows for 51 ACs. By kind: happy path 18, negative 16, security 14, compliance 14, regression 4.

**Questions raised in tickets** (the feedback loop, step 5): MR-101 QA-1, MR-104 QA-1, MR-105 QA-1 and QA-2, MR-106 QA-1, MR-109 QA-1 and QA-2. Rows that depend on an answer may change when the BA updates the spec.
