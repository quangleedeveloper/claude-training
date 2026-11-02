"""The persona's reply to one message: grounded in confirmed memories, in their way
of speaking, and refusing (without calling the model) when it has nothing to go on.

    identity question --> fixed reply
    retrieve --> grade --(relevant memories)--> generate (streamed) --> citations
                      \\--(none)--> fixed no-memory reply

Written as one generator instead of a LangGraph graph because a graph node cannot
stream tokens to its caller; the steps are the same as `ask_graph`.
"""

import re
import uuid
from collections.abc import Iterator, Sequence

from sqlmodel import Session

from app.core.config import settings
from app.core.llm import ChatTurn, LLMClient
from app.core.prompt import (
    PERSONA_IDENTITY_PATTERNS,
    PERSONA_IDENTITY_REPLY,
    PERSONA_NO_MEMORY,
    PERSONA_NOTICE,
    PERSONA_SYSTEM_PROMPT,
    PERSONA_USER_PROMPT,
)
from app.models import ConversationMessage, MessageRole, SearchHit
from app.services.ask_graph import format_context
from app.services.persona_events import DoneEvent, PersonaEvent, TokenEvent
from app.services.retrieval import persona_quotes, search_persona

CITATION = re.compile(r"\[(\d+)\]")


def is_identity_question(message: str, person_name: str) -> bool:
    """Whether the message asks if this is the real person (or a real person)."""
    patterns = [
        *PERSONA_IDENTITY_PATTERNS,
        rf"\bare you (?:really |actually |truly )?{re.escape(person_name)}"
        r"\s*(?:[?!.,]|\bor\b|$)",
    ]
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in patterns)


def retrieval_query(history: Sequence[ConversationMessage], message: str) -> str:
    """The new message plus the last two things the user said, so a follow-up such as
    "what did she grow there?" is searched together with what "there" refers to."""
    earlier = [m.content for m in history if m.role == MessageRole.USER][-2:]
    return "\n".join([*earlier, message])


def history_turns(history: Sequence[ConversationMessage]) -> list[ChatTurn]:
    """The latest turns of the open conversation as the model should see them. The
    opening notice is the app's text, not something the persona said."""
    spoken = [
        m
        for m in history
        if not (m.role == MessageRole.PERSONA and m.content == PERSONA_NOTICE)
    ]
    recent = spoken[-settings.PERSONA_HISTORY_TURNS :]
    return [
        ChatTurn("user" if m.role == MessageRole.USER else "assistant", m.content)
        for m in recent
    ]


def check_citations(text: str, sources: Sequence[SearchHit]) -> DoneEvent:
    """Map every [n] in the reply onto the numbered sources, setting aside the ones
    that point at nothing."""
    valid: list[int] = []
    invalid: list[int] = []
    for match in CITATION.finditer(text):
        number = int(match.group(1))
        target = valid if 1 <= number <= len(sources) else invalid
        if number not in target:
            target.append(number)
    return DoneEvent(
        sources=list(sources),
        fallback=False,
        cited_ids=[sources[number - 1].item.id for number in valid],
        invalid_citations=invalid,
        uncited=not valid,
    )


def reply(
    session: Session,
    llm: LLMClient,
    *,
    person_id: uuid.UUID,
    person_name: str,
    history: Sequence[ConversationMessage],
    message: str,
    summary: str | None = None,
) -> Iterator[PersonaEvent]:
    """Stream the persona's answer to `message`: tokens, then one done event."""
    if is_identity_question(message, person_name):
        yield TokenEvent(PERSONA_IDENTITY_REPLY)
        yield DoneEvent(sources=[], fallback=False)
        return

    hits = search_persona(session, person_id, llm, retrieval_query(history, message))
    memories = [hit for hit in hits if hit.score >= settings.MIN_RELEVANCE_SCORE]
    if not memories:
        # No context, no model call: a model asked with nothing invents a memory
        yield TokenEvent(PERSONA_NO_MEMORY)
        yield DoneEvent(sources=[], fallback=True)
        return

    quotes = persona_quotes(session, person_id, settings.PERSONA_STYLE_EXAMPLES)
    # Nothing may hold a database connection while the model streams
    session.rollback()

    examples = "\n".join(f'- "{quote.content}"' for quote in quotes) or "(none)"
    prompt = PERSONA_USER_PROMPT.format(
        memories=format_context(memories),
        examples=examples,
        summary=summary or "(none)",
        message=message,
    )
    turns = [*history_turns(history), ChatTurn("user", prompt)]

    parts: list[str] = []
    for chunk in llm.stream_answer(
        PERSONA_SYSTEM_PROMPT.format(person_name=person_name), turns
    ):
        parts.append(chunk)
        yield TokenEvent(chunk)
    yield check_citations("".join(parts), memories)
