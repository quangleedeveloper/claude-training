import uuid

from sqlmodel import Session

from app.models import ExtractedStatus, Memory, User
from app.services.ask_graph import NO_ANSWER, ask, format_context
from app.services.retrieval import search_extracted
from tests.utils.extracted_memory import create_random_extracted_memory
from tests.utils.llm import FakeLLMClient
from tests.utils.memory import create_random_memory
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
