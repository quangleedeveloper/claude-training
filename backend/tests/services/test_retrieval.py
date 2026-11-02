import uuid

from sqlmodel import Session

from app.models import ExtractedStatus, Memory, Person, User
from app.services.ask_graph import NO_ANSWER, ask, format_context
from app.services.retrieval import persona_quotes, search_extracted, search_persona
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.llm import FakeLLMClient
from tests.utils.memory import create_random_memory
from tests.utils.person import create_random_person
from tests.utils.user import get_superuser


def owner_of(db: Session, memory: Memory) -> User:
    user = db.get(User, memory.owner_id)
    assert user is not None
    return user


def test_search_ranks_the_closest_memory_first(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(db, memory, content="Grandma baked bread on Sundays")
    create_random_extracted_memory(db, memory, content="Dad repaired old bicycles")

    hits = search_extracted(db, owner_of(db, memory), llm_client, "who baked bread")

    assert hits[0].item.content == "Grandma baked bread on Sundays"
    assert hits[0].score > hits[1].score
    assert hits[0].memory_title == memory.title
    assert hits[0].person_name == memory.person_name


def test_search_never_returns_another_users_memories(
    db: Session, llm_client: FakeLLMClient
) -> None:
    mine = create_random_memory(db)
    theirs = create_random_memory(db)
    create_random_extracted_memory(db, mine, content="my secret recipe")
    create_random_extracted_memory(db, theirs, content="their secret recipe")

    hits = search_extracted(db, owner_of(db, mine), llm_client, "secret recipe")

    assert [h.item.content for h in hits] == ["my secret recipe"]


def test_search_keeps_a_superuser_to_their_own_memories_by_default(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(db, memory, content="zebra stripes tale")
    admin = get_superuser(db)

    default = search_extracted(db, admin, llm_client, "zebra stripes tale")
    everyone = search_extracted(
        db, admin, llm_client, "zebra stripes tale", all_users=True
    )

    assert all(h.item.memory_id != memory.id for h in default)
    assert everyone[0].item.content == "zebra stripes tale"


def test_search_ignores_all_users_for_a_normal_user(
    db: Session, llm_client: FakeLLMClient
) -> None:
    mine = create_random_memory(db)
    theirs = create_random_memory(db)
    create_random_extracted_memory(db, mine, content="giraffe neck tale")
    create_random_extracted_memory(db, theirs, content="giraffe neck tale again")

    hits = search_extracted(
        db, owner_of(db, mine), llm_client, "giraffe neck tale", all_users=True
    )

    assert [h.item.content for h in hits] == ["giraffe neck tale"]


def test_ask_by_a_superuser_only_uses_their_own_memories_unless_asked(
    db: Session, llm_client: FakeLLMClient
) -> None:
    theirs = create_random_memory(db)
    create_random_extracted_memory(db, theirs, content="Cousin Ana raised llamas")
    admin = get_superuser(db)

    default = ask(db, admin, llm_client, "Cousin Ana raised llamas")
    everyone = ask(db, admin, llm_client, "Cousin Ana raised llamas", all_users=True)

    assert default.sources == []
    assert [s.item.content for s in everyone.sources] == ["Cousin Ana raised llamas"]


def test_search_skips_rejected_items_and_can_focus_on_one_memory(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    other = create_random_memory(db)
    other.owner_id = memory.owner_id
    db.add(other)
    db.commit()
    create_random_extracted_memory(
        db, memory, content="rejected lemon tart", status=ExtractedStatus.REJECTED
    )
    create_random_extracted_memory(db, memory, content="lemon tart in memory one")
    create_random_extracted_memory(db, other, content="lemon tart in memory two")
    user = owner_of(db, memory)

    everywhere = search_extracted(db, user, llm_client, "lemon tart")
    focused = search_extracted(db, user, llm_client, "lemon tart", memory_id=memory.id)

    assert {h.item.content for h in everywhere} == {
        "lemon tart in memory one",
        "lemon tart in memory two",
    }
    assert [h.item.content for h in focused] == ["lemon tart in memory one"]


def test_ask_answers_from_relevant_memories_and_cites_them(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(
        db, memory, content="Grandma baked bread on Sundays", people=["Grandma"]
    )

    response = ask(db, owner_of(db, memory), llm_client, "who baked bread on Sundays")

    assert response.answer == "Fake answer citing [1]."
    assert [s.item.content for s in response.sources] == [
        "Grandma baked bread on Sundays"
    ]
    assert "[1] Grandma baked bread on Sundays" in llm_client.answer_prompts[0]


def test_ask_does_not_guess_when_nothing_is_relevant(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(db, memory, content="Grandma baked bread")

    response = ask(
        db, owner_of(db, memory), llm_client, "quantum chromodynamics lecture"
    )

    assert response.answer == NO_ANSWER
    assert response.sources == []
    assert llm_client.answer_prompts == []


def test_ask_scoped_to_a_memory_ignores_the_others(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    create_random_extracted_memory(db, memory, content="blue boat on the river")

    response = ask(
        db, owner_of(db, memory), llm_client, "blue boat on the river", uuid.uuid4()
    )

    assert response.answer == NO_ANSWER


def test_format_context_lists_the_details(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    extracted = create_random_extracted_memory(
        db, memory, content="Wedding by the sea", people=["Mum", "Dad"]
    )
    extracted.event_date_text = "June 1975"
    extracted.location = "Brighton"
    db.add(extracted)
    db.commit()

    hits = search_extracted(db, owner_of(db, memory), llm_client, "wedding")
    text = format_context(hits)

    assert text.startswith("[1] Wedding by the sea (")
    assert "when: June 1975" in text
    assert "where: Brighton" in text
    assert "people: Mum, Dad" in text


def test_format_context_leaves_out_a_missing_person_name(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    memory.person_name = ""
    db.add(memory)
    create_random_extracted_memory(db, memory, content="Wedding by the sea")
    db.commit()

    hits = search_extracted(db, owner_of(db, memory), llm_client, "wedding")
    text = format_context(hits)

    assert "about" not in text
    assert f"story: {memory.title}" in text


def persona_memory(db: Session) -> tuple[Person, Memory]:
    """A person and one of their owner's memories, linked to them."""
    person = create_random_person(db)
    owner = db.get(User, person.owner_id)
    memory = create_random_memory(db, owner)
    memory.person_id = person.id
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return person, memory


def test_search_persona_skips_unconfirmed(
    db: Session, llm_client: FakeLLMClient
) -> None:
    person, memory = persona_memory(db)
    confirmed = create_random_extracted_memory(
        db, memory, content="Grandma baked bread on Sundays", confirmed=True
    )
    create_random_extracted_memory(db, memory, content="Grandma baked bread daily")

    hits = search_persona(db, person.id, llm_client, "who baked bread")

    assert [h.item.id for h in hits] == [confirmed.id]
    assert hits[0].item.confirmed is True
    assert hits[0].memory_title == memory.title
    # Undoing the confirmation takes it out again
    confirmed.confirmed_at = None
    db.add(confirmed)
    db.commit()
    assert search_persona(db, person.id, llm_client, "who baked bread") == []


def test_search_persona_skips_rejected_confirmed(
    db: Session, llm_client: FakeLLMClient
) -> None:
    person, memory = persona_memory(db)
    create_random_extracted_memory(
        db,
        memory,
        content="Grandma baked bread on Sundays",
        status=ExtractedStatus.REJECTED,
        confirmed=True,
    )

    assert search_persona(db, person.id, llm_client, "who baked bread") == []


def test_search_persona_only_this_persons_memories(
    db: Session, llm_client: FakeLLMClient
) -> None:
    person, memory = persona_memory(db)
    owner = db.get(User, person.owner_id)
    other_person = create_random_person(db, owner)
    other_memory = create_random_memory(db, owner)
    other_memory.person_id = other_person.id
    db.add(other_memory)
    db.commit()
    unlinked = create_random_memory(db, owner)
    mine = create_random_extracted_memory(
        db, memory, content="Grandma baked bread", confirmed=True
    )
    create_random_extracted_memory(
        db, other_memory, content="Grandpa baked bread", confirmed=True
    )
    create_random_extracted_memory(
        db, unlinked, content="Aunt baked bread", confirmed=True
    )

    hits = search_persona(db, person.id, llm_client, "who baked bread")

    assert [h.item.id for h in hits] == [mine.id]


def test_search_persona_respects_the_limit(
    db: Session, llm_client: FakeLLMClient
) -> None:
    person, memory = persona_memory(db)
    for number in range(3):
        create_random_extracted_memory(
            db, memory, content=f"Bread story {number}", confirmed=True
        )

    assert len(search_persona(db, person.id, llm_client, "bread", limit=2)) == 2


def test_search_extracted_still_finds_unconfirmed_items(
    db: Session, llm_client: FakeLLMClient
) -> None:
    memory = create_random_memory(db)
    item = create_random_extracted_memory(db, memory, content="Grandma baked bread")

    hits = search_extracted(db, owner_of(db, memory), llm_client, "bread")

    assert [h.item.id for h in hits] == [item.id]
    assert hits[0].item.confirmed is False


def test_persona_quotes_are_confirmed_quotes_newest_first(db: Session) -> None:
    person, memory = persona_memory(db)
    older = create_random_extracted_memory(
        db, memory, content="Older quote.", category="quote", confirmed=True
    )
    newer = create_random_extracted_memory(
        db, memory, content="Newer quote.", category="quote", confirmed=True
    )
    create_random_extracted_memory(
        db, memory, content="Not confirmed.", category="quote"
    )
    create_random_extracted_memory(
        db,
        memory,
        content="Rejected.",
        category="quote",
        status=ExtractedStatus.REJECTED,
        confirmed=True,
    )
    create_random_extracted_memory(
        db, memory, content="A fact.", category="fact", confirmed=True
    )
    elsewhere = create_random_memory(db, db.get(User, person.owner_id))
    create_random_extracted_memory(
        db, elsewhere, content="Unlinked.", category="quote", confirmed=True
    )

    quotes = persona_quotes(db, person.id, limit=10)

    assert [q.id for q in quotes] == [newer.id, older.id]
    assert [q.id for q in persona_quotes(db, person.id, limit=1)] == [newer.id]
