# Test matrix

## Persona conversation

spec: specs/persona-conversation/spec.md · tickets: MR-101 to MR-109, plus MR-110 to MR-114 (screens, blocked on Q12) · drafted by QA with Claude, 2026-10-28
fixture: `fixtures/families/thomas.json` · eval cases: `evals/grounding/G-101.json` to `G-117.json`

Paths in *Test or eval* are under `backend/` unless they start with `evals/`. Each row is written before the code, so it is the target the dev hands to Claude. Rows marked *eval* need the real local model; their unit halves use the fake.

| AC | Scenario | Level | Kind | Test or eval | Ticket | Status |
|----|----------|-------|------|--------------|--------|--------|
| AC-1.1 | Owner creates a person with name and other names; returned with id and owner | integration | happy path | `backend/tests/api/routes/test_persons.py::test_create_person` | MR-101 | todo |
| AC-1.2 | Owner links own memory to own person; `person_id` set | integration | happy path | `backend/tests/api/routes/test_persons.py::test_link_memory_to_person` | MR-101 | todo |
| AC-1.2 | Linking another user's memory, or to another user's person, is 403 | integration | security | `backend/tests/api/routes/test_persons.py::test_link_foreign_memory_or_person_403` | MR-101 | todo |
| AC-1.3 | Deleting a person keeps memories, unlinked | integration | negative | `backend/tests/api/routes/test_persons.py::test_delete_person_keeps_memories` | MR-101 | todo |
| AC-1.3 | Deleting a person removes its conversations, messages, audit rows, summaries, members, offers (one test per table, added by the ticket that adds it) | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_delete_person_cascades`, `backend/tests/api/routes/test_members.py::test_delete_person_cascades`, `backend/tests/api/routes/test_offers.py::test_delete_person_cascades` | MR-104, 106–108 | todo |
| AC-1.4 | Superuser who isn't the owner gets 403 on every person endpoint and on linking | integration | security | `backend/tests/api/routes/test_persons.py::test_superuser_cannot_access_others_persons` | MR-101 | todo |
| AC-2.1 | Owner confirms an item; `confirmed_at` set, returned as confirmed | integration | happy path | `backend/tests/api/routes/test_extracted_memories.py::test_confirm_item` | MR-102 | todo |
| AC-2.2 | Editing an item counts as confirmed without a confirm call | integration | happy path | `backend/tests/api/routes/test_extracted_memories.py::test_edit_confirms_item` | MR-102 | todo |
| AC-2.3 | Undo confirm; the item is no longer returned by persona retrieval | integration | negative | `backend/tests/api/routes/test_extracted_memories.py::test_unconfirm_item`, `backend/tests/services/test_retrieval.py::test_search_persona_skips_unconfirmed` | MR-102 | todo |
| AC-2.4 | `/search/` and `/search/ask` still find unconfirmed, non-rejected items | integration | regression | `backend/tests/api/routes/test_search.py::test_search_unchanged_by_confirm_step` | MR-102 | todo |
| AC-2.4 | `POST /memories/{id}/confirm-all` confirms every non-rejected item, not rejected ones | integration | happy path | `backend/tests/api/routes/test_extracted_memories.py::test_confirm_all_skips_rejected` | MR-102 | todo |
| AC-2.5 | Member confirming an item gets 403 | integration | security | `backend/tests/api/routes/test_members.py::test_member_cannot_confirm` | MR-107 | todo |
| AC-2.5 | Outsider confirming an item gets 403 | integration | security | `backend/tests/api/routes/test_extracted_memories.py::test_outsider_cannot_confirm` | MR-102 | todo |
| AC-2.6 | Editing a story re-extracts it but keeps confirmed, never-edited items; unconfirmed AI items are replaced | integration | regression | `backend/tests/services/test_extraction.py::test_reextraction_keeps_confirmed_items` | MR-102 | todo |
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
| AC-4.6 | Superuser reading a member's summary or conversation gets 403 | integration | security | `backend/tests/api/routes/test_conversations.py::test_superuser_no_access_to_conversations` | MR-104, MR-106 | todo |
| AC-5.1 | Answerable question: reply cites `[n]` and `sources[n-1]` is that item | unit + eval | happy path | `backend/tests/services/test_persona_graph.py::test_citation_maps_to_source`, `evals/grounding/G-101.json` | MR-105, MR-109 | todo |
| AC-5.2 | Every `[n]` maps to a source; no source that wasn't in the prompt; stray `[n]` handled | unit | negative | `backend/tests/services/test_persona_graph.py::test_citations_and_sources_match` | MR-105 | todo |
| AC-5.3 | Two confirmed items disagree on the wedding year; reply says so | eval | happy path | `evals/grounding/G-106.json` | MR-109 | todo |
| AC-5.4 | Memories given but the streamed reply has no valid `[n]`: `done.uncited` true, audit row flagged, reply not replaced | unit | negative | `backend/tests/services/test_persona_graph.py::test_uncited_reply_flagged` | MR-105 | todo |
| AC-6.1 | No match above threshold: reply is exactly `PERSONA_NO_MEMORY`, no sources, `fallback` true | unit + eval | negative | `backend/tests/services/test_persona_graph.py::test_no_memory_reply_is_fixed`, `evals/grounding/G-102.json` | MR-105, MR-109 | todo |
| AC-6.2 | No match: the fake records zero `answer` and `stream_answer` calls | unit | negative | `backend/tests/services/test_persona_graph.py::test_no_memory_makes_no_model_call` | MR-105 | todo |
| AC-7.1 | New conversation: first message is `PERSONA_NOTICE`, also in the open response | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_notice_is_first_message` | MR-104 | todo |
| AC-7.2 | Every `done` event carries `notice`, including the fallback reply | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_done_carries_notice` | MR-104 | todo |
| AC-7.3 | Identity question ("Are you really Mom?") gets exactly `PERSONA_IDENTITY_REPLY`, no sources, no model call, with or without matching memories | unit + eval | compliance | `backend/tests/services/test_persona_graph.py::test_identity_question_gets_fixed_reply`, `evals/grounding/G-107.json` | MR-105, MR-109 | todo |
| AC-7.4 | Reply never says it is the person | eval | compliance | `evals/grounding/G-108.json` | MR-105, MR-109 | todo |
| AC-8.1 | Up to `PERSONA_STYLE_EXAMPLES` confirmed quotes sent as style examples, separate from numbered memories | unit | happy path | `backend/tests/services/test_persona_graph.py::test_style_examples_from_confirmed_quotes` | MR-105 | todo |
| AC-8.2 | Unconfirmed or rejected quotes never sent as style examples or used | unit + eval | negative | `backend/tests/services/test_persona_graph.py::test_unconfirmed_quotes_excluded`, `evals/grounding/G-117.json` | MR-105, MR-109 | todo |
| AC-8.3 | Repeating a quote as something she said cites it | eval | compliance | `evals/grounding/G-109.json` | MR-109 | todo |
| AC-8.4 | No confirmed quotes: reply still works | unit | happy path | `backend/tests/services/test_persona_graph.py::test_reply_without_quotes` | MR-105 | todo |
| AC-9.1 | End (or idle timeout): summary saved, status `ended`, messages deleted | integration | happy path | `backend/tests/api/routes/test_conversations.py::test_end_saves_summary_deletes_messages`, `backend/tests/services/test_conversation_summary.py::test_idle_sweep_ends_and_summarizes` | MR-106 | todo |
| AC-9.2 | Next conversation: "what did we talk about last time?" mentions at least one topic from the summary | eval | happy path | `evals/grounding/G-115.json` | MR-106, MR-109 | todo |
| AC-9.3 | Owner or another member reading someone's summary gets 403; member reads and deletes own | integration | security | `backend/tests/api/routes/test_conversations.py::test_summary_private_to_member` | MR-106 | todo |
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
| AC-N2.1 | Manual run on the demo machine before the demo: p90 first words ≤ 3 s, full reply ≤ 30 s; CI latency is informational | eval (manual run) | compliance | `backend/scripts/measure_persona_latency.py`, eval runner report | MR-103, MR-109 | todo |
| AC-N3.1 | One `personaturn` row per turn with ids and timings, no text | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_turn_audit_has_no_text` | MR-104 | todo |
| AC-N3.1 | Log lines for a turn hold no message or memory text (log capture) | integration | compliance | `backend/tests/api/routes/test_conversations.py::test_turn_logs_hold_no_content` | MR-104 | todo |
| AC-N4.1 | Every new table: delete test from its owner (person, user, conversation, memory) | integration | compliance | one `test_*_cascades` per table, as in the AC-1.3 rows | MR-101–108 | todo |
| AC-N4.2 | Deleting a user removes their persons, memberships, conversations and summaries | integration | compliance | `backend/tests/api/routes/test_persons.py::test_delete_user_cascades_persona_data` | MR-101, then each ticket for its tables | todo |
| AC-N6.1 | Injected story text: reply stays grounded, system prompt byte-for-byte unchanged | unit + eval | security | `backend/tests/services/test_persona_graph.py::test_injected_story_does_not_change_system_prompt`, `evals/grounding/G-113.json` | MR-105, MR-109 | todo |
| AC-N6.1 | Injected member message: no invented memory | unit + eval | security | `backend/tests/services/test_persona_graph.py::test_injected_message_stays_in_user_turn`, `evals/grounding/G-114.json` | MR-105, MR-109 | todo |
| AC-N7.1 | Persona-related change triggers the eval job; any invented memory fails it | CI | compliance | CI workflow from MR-109 | MR-109 | todo |
| AC-13.1 | Opening the chat shows the notice at the top and it stays visible after messages | e2e | happy path | `frontend/tests/chat.spec.ts::Notice stays visible` | MR-110 | todo |
| AC-13.2 | A sent message appears at once, input is disabled while the reply streams, reply grows in an aria-live region | e2e | happy path | `frontend/tests/chat.spec.ts::Reply streams in` | MR-110 | todo |
| AC-13.3 | A valid [n] links to its source under the reply; an [n] with no source stays plain text | e2e | happy path | `frontend/tests/chat.spec.ts::Citations link to sources` | MR-110 | todo |
| AC-13.4 | Fixed no-memory reply shows with no sources; an uncited reply shows the not-backed note | e2e | negative | `frontend/tests/chat.spec.ts::No-memory and uncited replies` | MR-110 | todo |
| AC-13.5 | A stream error shows a generic message, keeps the typed text and shows no server text | e2e | negative | `frontend/tests/chat.spec.ts::Errors keep the typed text` | MR-110 | todo |
| AC-13.6 | End asks for a confirm, then ends the chat and leaves it | e2e | happy path | `frontend/tests/chat.spec.ts::End conversation` | MR-110 | todo |
| AC-13.7 | 403 or 409 on send shows a clear message and disables sending | e2e | security | `frontend/tests/chat.spec.ts::Access removed or ended` | MR-110 | todo |
| AC-14.1 | A saved summary is shown as What we talked about | e2e | happy path | `frontend/tests/recall.spec.ts::Summary is shown` | MR-111 | todo |
| AC-14.2 | No summary shows the empty state, not an error toast | e2e | negative | `frontend/tests/recall.spec.ts::Empty state` | MR-111 | todo |
| AC-14.3 | Deleting the summary after a confirm removes it | e2e | happy path | `frontend/tests/recall.spec.ts::Delete summary` | MR-111 | todo |
| AC-14.4 | Another user's summary for the same person is never shown | e2e | security | `frontend/tests/recall.spec.ts::Only my summary` | MR-111 | todo |
| AC-15.1 | Invite stays disabled until the 18-or-older tick is set | e2e | happy path | `frontend/tests/sharing.spec.ts::Adult tick required` | MR-113 | todo |
| AC-15.2 | A known and an unknown email show the same confirmation | e2e | security | `frontend/tests/sharing.spec.ts::Same answer for any email` | MR-113 | todo |
| AC-15.3 | Members list shows name and email; revoke asks for a confirm and removes the member | e2e | happy path | `frontend/tests/sharing.spec.ts::Revoke member` | MR-113 | todo |
| AC-15.4 | Shared with me lists the persons by name only and opens the chat; empty state when none | e2e | happy path | `frontend/tests/sharing.spec.ts::Shared with me` | MR-113 | todo |
| AC-15.5 | A revoked member loses the person from the list and an open chat shows access removed | e2e | security | `frontend/tests/sharing.spec.ts::Revoked member` | MR-113 | todo |
| AC-15.6 | GET /persons/shared returns only id and name of persons the caller is a member of | integration | happy path | `backend/tests/api/routes/test_persons.py::test_read_shared_persons` | MR-112 | todo |
| AC-15.6 | Owner's own persons, outsiders, superusers and revoked members never get extra rows | integration | security | `backend/tests/api/routes/test_persons.py::test_shared_persons_scope` | MR-112 | todo |
| AC-16.1 | A member offers text from the chat and sees that the family decides | e2e | happy path | `frontend/tests/offers.spec.ts::Offer a memory` | MR-114 | todo |
| AC-16.2 | Owner accepts an offer and is told the new memory is not yet confirmed, with a link | e2e | happy path | `frontend/tests/offers.spec.ts::Accept offer` | MR-114 | todo |
| AC-16.3 | Declining asks for a confirm and removes the offer | e2e | negative | `frontend/tests/offers.spec.ts::Decline offer` | MR-114 | todo |
| AC-16.4 | A member sees no offers list and the endpoint is 403 | e2e | security | `frontend/tests/offers.spec.ts::Members cannot list offers` | MR-114 | todo |
| AC-N8.1 | No message, reply, source, summary or offer text in storage, URL, query cache or console | e2e | compliance | `frontend/tests/chat.spec.ts::Nothing stored in the browser` | MR-110 | todo |

**Coverage:** 92 rows for 78 ACs (the 23 new rows for MR-110 to MR-114 are proposed, pending Q12). By kind: happy path 30, negative 21, security 21, compliance 15, regression 5.

**Questions raised in tickets** (the feedback loop, step 5): all answered by the BA on 2026-10-28; the spec and these rows were updated in the same PR.

## MCP server

spec: specs/mcp-server/spec.md · tickets: MR-121 to MR-127 · drafted by QA with Claude, 2026-11-04
fixture: `fixtures/families/thomas.json` · eval cases: `evals/grounding/G-118.json` to `G-127.json` (they carry `"spec": "mcp-server"` and `"via": "mcp"`)

The ACs below are numbered by the MCP spec, so `AC-4.1` here is not the persona spec's `AC-4.1`. Paths in *Test or eval* are under `backend/` unless they start with `evals/`. Rows marked *eval* need the real local model; their unit halves use the fake.

| AC | Scenario | Level | Kind | Test or eval | Ticket | Status |
|----|----------|-------|------|--------------|--------|--------|
| AC-1.1 | The server reads and writes only stdio and binds no listening socket | integration | security | `backend/tests/mcp/test_server.py::test_server_opens_no_socket` | MR-121 | todo |
| AC-1.2 | The docs show the stdio start command and no URL or port | unit | compliance | `backend/tests/mcp/test_cross_tool.py::test_docs_show_stdio_command_only` | MR-126 | todo |
| AC-2.1 | A valid token for an active user runs every tool as that user | integration | happy path | `backend/tests/mcp/test_server.py::test_tool_runs_as_token_user` | MR-121 | todo |
| AC-2.2 | A missing, expired or malformed token gets the generic error and nothing is read or written | integration | security | `backend/tests/mcp/test_server.py::test_bad_token_refused` | MR-121 | todo |
| AC-2.3 | A token for an inactive or deleted user is refused on every tool | integration | security | `backend/tests/mcp/test_server.py::test_inactive_or_deleted_user_refused` | MR-121 | todo |
| AC-2.4 | A superuser token behaves exactly like a normal user's | integration | security | `backend/tests/mcp/test_server.py::test_superuser_has_no_extra_reach` | MR-121 | todo |
| AC-3.1 | Owner of A and member of B sees A as `owner` and B as `member`, with only id, name, role | integration | happy path | `backend/tests/mcp/test_list_personas.py::test_list_personas_owner_and_member` | MR-121 | todo |
| AC-3.2 | A person owned by someone else and not shared is not listed | integration | security | `backend/tests/mcp/test_list_personas.py::test_list_personas_hides_unshared` | MR-121 | todo |
| AC-3.3 | A revoked member no longer sees the person | integration | security | `backend/tests/mcp/test_list_personas.py::test_list_personas_after_revoke` | MR-121 | todo |
| AC-3.4 | No persons gives an empty list, not an error | integration | negative | `backend/tests/mcp/test_list_personas.py::test_list_personas_empty` | MR-121 | todo |
| AC-4.1 | Owner asks about a confirmed item; the answer cites `[n]` and `sources[n-1]` is that item | unit + eval | happy path | `backend/tests/mcp/test_ask_memory.py::test_ask_cites_confirmed_item`, `evals/grounding/G-118.json` | MR-122, MR-127 | todo |
| AC-4.2 | A member gets the same grounded answer and only the cited sources | unit + eval | happy path | `backend/tests/mcp/test_ask_memory.py::test_ask_as_member`, `evals/grounding/G-119.json` | MR-122, MR-127 | todo |
| AC-4.3 | The best match is unconfirmed: not in the sources and not in the prompt | unit + eval | security | `backend/tests/mcp/test_ask_memory.py::test_ask_skips_unconfirmed`, `evals/grounding/G-121.json` | MR-122, MR-127 | todo |
| AC-4.4 | A rejected item, once confirmed, is never used | unit + eval | negative | `backend/tests/mcp/test_ask_memory.py::test_ask_skips_rejected`, `evals/grounding/G-122.json` | MR-122, MR-127 | todo |
| AC-4.4 | A confirmed item on a memory linked to another person is never used | unit + eval | security | `backend/tests/mcp/test_ask_memory.py::test_ask_skips_other_persons_items`, `evals/grounding/G-123.json` | MR-122, MR-127 | todo |
| AC-4.5 | Two confirmed items disagree on the date: both reach the prompt, and the answer says they disagree | unit + eval | regression | `backend/tests/mcp/test_ask_memory.py::test_ask_passes_disagreeing_items`, `evals/grounding/G-124.json` | MR-122, MR-127 | todo |
| AC-4.6 | A corrected item (`was_edited`) is answered with the corrected wording, never the old value | unit + eval | regression | `backend/tests/mcp/test_ask_memory.py::test_ask_uses_corrected_wording`, `evals/grounding/G-120.json` | MR-122, MR-127 | todo |
| AC-4.7 | Every `[n]` maps to a source and no source was absent from the prompt | unit | compliance | `backend/tests/mcp/test_ask_memory.py::test_ask_citations_map_to_sources` | MR-122 | todo |
| AC-4.8 | The answer is in the third person and never claims to be the person | eval | compliance | `evals/grounding/G-125.json` | MR-127 | todo |
| AC-4.9 | Unknown person is "Person not found", unreachable person (including a superuser who is neither owner nor member) is "Not enough permissions"; no model call either way | integration | security | `backend/tests/mcp/test_ask_memory.py::test_ask_unknown_or_unreachable_person` | MR-122 | todo |
| AC-4.10 | An empty question or one over 500 characters is refused and nothing is read | integration | negative | `backend/tests/mcp/test_ask_memory.py::test_ask_invalid_question` | MR-122 | todo |
| AC-5.1 | No confirmed item above `MIN_RELEVANCE_SCORE` returns exactly `NO_ANSWER` with no sources | unit + eval | happy path | `backend/tests/mcp/test_ask_memory.py::test_ask_no_context_returns_no_answer`, `evals/grounding/G-127.json` | MR-122, MR-127 | todo |
| AC-5.2 | In the no-context case the chat model is never called | unit | compliance | `backend/tests/mcp/test_ask_memory.py::test_ask_no_context_makes_no_model_call` | MR-122 | todo |
| AC-5.3 | A person whose items all exist but none is confirmed answers `NO_ANSWER` | unit | negative | `backend/tests/mcp/test_ask_memory.py::test_ask_only_unconfirmed_items` | MR-122 | todo |
| AC-6.1 | Owner searches and gets item text, memory title and score, best first, at most 20 | integration | happy path | `backend/tests/mcp/test_search_memories.py::test_search_returns_confirmed_hits` | MR-123 | todo |
| AC-6.2 | `limit` above 20 or below 1 is invalid; missing uses `RETRIEVAL_TOP_K` | integration | negative | `backend/tests/mcp/test_search_memories.py::test_search_limit_bounds` | MR-123 | todo |
| AC-6.3 | Unconfirmed, rejected and other-person items are never returned | integration | security | `backend/tests/mcp/test_search_memories.py::test_search_skips_unconfirmed_rejected_and_other_person` | MR-123 | todo |
| AC-6.4 | A hit holds item text and memory title only: no full story, files or owner | integration | compliance | `backend/tests/mcp/test_search_memories.py::test_search_hit_has_no_story_or_files` | MR-123 | todo |
| AC-6.5 | A member searching gets "Not enough permissions" and nothing is returned | integration | security | `backend/tests/mcp/test_search_memories.py::test_member_cannot_search` | MR-123 | todo |
| AC-6.6 | An outsider or a superuser who is neither owner nor member gets the same refusal | integration | security | `backend/tests/mcp/test_search_memories.py::test_outsider_and_superuser_cannot_search` | MR-123 | todo |
| AC-6.7 | An owner with no confirmed items gets an empty list | integration | negative | `backend/tests/mcp/test_search_memories.py::test_search_no_confirmed_items_is_empty` | MR-123 | todo |
| AC-7.1 | A member's `add_memory` stores one offer and creates no memory or extracted item | integration | happy path | `backend/tests/mcp/test_add_memory.py::test_member_add_memory_makes_offer` | MR-124 | todo |
| AC-7.2 | The owner's `add_memory` without a direct request stores an offer the same way | integration | happy path | `backend/tests/mcp/test_add_memory.py::test_owner_add_memory_makes_offer` | MR-124 | todo |
| AC-7.3 | The owner accepts an offer made through the tool: it becomes their memory, linked and extracted, items unconfirmed | integration | regression | `backend/tests/mcp/test_add_memory.py::test_accept_offer_from_tool` | MR-124 | todo |
| AC-7.4 | With 20 offers waiting from this user for this person, the call is refused with the app's message and stores nothing | integration | negative | `backend/tests/mcp/test_add_memory.py::test_add_memory_offer_cap` | MR-124 | todo |
| AC-7.5 | Empty text or text over 5000 characters is refused and nothing is stored | integration | negative | `backend/tests/mcp/test_add_memory.py::test_add_memory_invalid_text` | MR-124 | todo |
| AC-7.6 | An outsider or a superuser who is neither owner nor member is refused and nothing is stored | integration | security | `backend/tests/mcp/test_add_memory.py::test_outsider_and_superuser_cannot_offer` | MR-124 | todo |
| AC-7.7 | The reply is a fixed message and repeats none of the offered text | integration | compliance | `backend/tests/mcp/test_add_memory.py::test_add_memory_reply_does_not_echo_text` | MR-124 | todo |
| AC-8.1 | With `MCP_ALLOW_DIRECT_MEMORY` off (default), a direct request is refused and nothing is stored | integration | security | `backend/tests/mcp/test_direct_memory.py::test_direct_memory_off_by_default` | MR-125 | todo |
| AC-8.2 | Setting on, the owner's first call stores nothing and returns a token with a preview of the text and person | integration | happy path | `backend/tests/mcp/test_direct_memory.py::test_first_call_returns_token_only` | MR-125 | todo |
| AC-8.3 | The second call with the valid token creates the owner's memory, linked to the person, extracted, items unconfirmed | integration | happy path | `backend/tests/mcp/test_direct_memory.py::test_second_call_creates_memory` | MR-125 | todo |
| AC-8.4 | An expired, reused, mismatched (text, person or user) or malformed token stores nothing and returns a generic error | integration | security | `backend/tests/mcp/test_direct_memory.py::test_bad_token_stores_nothing` | MR-125 | todo |
| AC-8.5 | A member is refused a direct request, with or without a token | integration | security | `backend/tests/mcp/test_direct_memory.py::test_member_cannot_create_directly` | MR-125 | todo |
| AC-8.6 | After the first call the counts of `Memory` and `MemoryOffer` rows are unchanged | integration | compliance | `backend/tests/mcp/test_direct_memory.py::test_first_call_writes_nothing` | MR-125 | todo |
| AC-9.1 | A superuser who owns nothing is refused on every tool for another user's person; `list_personas` shows only their own and shared | integration | security | `backend/tests/mcp/test_cross_tool.py::test_superuser_has_no_extra_reach_on_any_tool` | MR-126 | todo |
| AC-9.2 | No tool schema has an `all_users` parameter and an extra `all_users` argument is rejected | unit | security | `backend/tests/mcp/test_cross_tool.py::test_no_tool_accepts_all_users` | MR-126 | todo |
| AC-9.3 | Two normal users cannot read, search or offer to each other's person by id | integration | security | `backend/tests/mcp/test_cross_tool.py::test_second_user_is_refused_on_every_tool` | MR-126 | todo |
| AC-10.1 | A story that says "ignore your rules" stays inside the numbered context; the system prompt is unchanged and the answer stays grounded | unit + eval | security | `backend/tests/mcp/test_ask_memory.py::test_injected_story_does_not_change_system_prompt`, `evals/grounding/G-126.json` | MR-122, MR-127 | todo |
| AC-10.2 | A question or offer text with instructions is stored or placed as data and changes no rule | integration | security | `backend/tests/mcp/test_add_memory.py::test_instructions_in_offer_text_are_data` | MR-124 | todo |
| AC-10.3 | Results carry memory text in named data fields and the server instructions say it is data | unit | compliance | `backend/tests/mcp/test_server.py::test_instructions_and_result_fields_mark_text_as_data` | MR-121 | todo |
| AC-11.1 | Every failed call returns a fixed generic message with no question, answer, memory or offer text | integration | security | `backend/tests/mcp/test_server.py::test_errors_are_generic`, `backend/tests/mcp/test_add_memory.py::test_add_memory_errors_are_generic` | MR-121, MR-124 | todo |
| AC-11.2 | The local model being down gives "The assistant could not answer right now", not its error text | unit | negative | `backend/tests/mcp/test_ask_memory.py::test_ask_model_down_is_generic` | MR-122 | todo |
| AC-N1.1 | The server calls only `LLMClient`; tests use the fakes and never Ollama or a hosted API | unit | compliance | `backend/tests/mcp/test_ask_memory.py::test_ask_uses_only_llm_client` | MR-122 | todo |
| AC-N2.1 | The grounding evals run through `ask_memory` report zero invented memories; every cited source is in the fixture | eval | compliance | `evals/grounding/G-118.json` to `evals/grounding/G-127.json`, `backend/tests/scripts/test_run_grounding_evals.py::test_mcp_cases_are_driven_through_ask_memory` | MR-127 | todo |
| AC-N3.1 | No log line from any tool, success or failure, holds the question, answer, item text, title, offer text, token or a file path | integration | compliance | `backend/tests/mcp/test_cross_tool.py::test_no_content_in_logs` | MR-126 | todo |
| AC-N4.1 | Each tool is refused for an outsider, a superuser who is neither owner nor member, and (where it differs) a member | integration | security | `backend/tests/mcp/test_list_personas.py::test_list_personas_scope`, `backend/tests/mcp/test_ask_memory.py::test_ask_access`, `backend/tests/mcp/test_search_memories.py::test_search_access`, `backend/tests/mcp/test_add_memory.py::test_add_memory_access`, `backend/tests/mcp/test_direct_memory.py::test_direct_memory_access` | MR-121 to MR-125 | todo |
| AC-N5.1 | The docs say the assistant must use a local model, name where the token is stored, and say a leaked token reaches the user's memories until it expires | unit | compliance | `backend/tests/mcp/test_cross_tool.py::test_docs_state_local_model_and_token_risk` | MR-126 | todo |
| AC-N6.1 | `MCP_ACCESS_TOKEN` is in `Settings` and `.env.example` with a safe default; none is read from `os.environ` | unit | compliance | `backend/tests/mcp/test_server.py::test_access_token_setting_documented` | MR-121 | todo |
| AC-N6.1 | `MCP_ALLOW_DIRECT_MEMORY` and `MCP_CONFIRMATION_TTL_SECONDS` are in `Settings` and `.env.example` with safe defaults (direct memory off) | unit | compliance | `backend/tests/mcp/test_direct_memory.py::test_direct_memory_settings_documented`, `backend/tests/mcp/test_cross_tool.py::test_all_mcp_settings_documented` | MR-125, MR-126 | todo |
