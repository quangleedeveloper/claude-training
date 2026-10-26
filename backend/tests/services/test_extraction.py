import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, col, select

from app.core.checkpoint import clear_thread, open_checkpointer
from app.core.config import settings
from app.models import ExtractedMemory, ExtractedSource, ExtractedStatus
from app.services.extraction import (
    CHUNK_CHARS,
    ExtractedDraft,
    RawItem,
    chunk_text,
    embedding_text,
    filter_items,
    normalize,
    parse_items,
    replace_extracted,
)
from app.services.extraction_graph import (
    build_extraction_graph,
    drafts_from_state,
    run_extraction,
)
from tests.utils.llm import FakeLLMClient
from tests.utils.memory import create_random_memory
from tests.utils.memory_file import FakeMediaProcessor


def item(content: str, confidence: float = 0.9) -> RawItem:
    return RawItem.model_validate(
        {"category": "fact", "content": content, "confidence": confidence}
    )


def test_normalize_ignores_case_spacing_and_punctuation() -> None:
    assert normalize("  Grandma  BAKED bread! ") == normalize("grandma baked bread")


def test_chunk_text_keeps_short_text_whole() -> None:
    assert chunk_text("One. Two. Three.") == ["One. Two. Three."]


def test_chunk_text_splits_on_sentence_boundaries() -> None:
    sentence = "x" * 1000 + "."
    chunks = chunk_text(" ".join([sentence] * 7))
    # Two sentences fit in a chunk, the third would overflow it
    assert len(chunks) == 4
    assert all(len(chunk) <= CHUNK_CHARS for chunk in chunks)
    assert all(chunk.endswith(".") for chunk in chunks)


def test_chunk_text_cuts_a_run_with_no_punctuation() -> None:
    chunks = chunk_text("word " * 2000)
    assert len(chunks) > 1
    assert all(len(chunk) <= CHUNK_CHARS for chunk in chunks)


def test_chunk_text_of_blank_text_is_empty() -> None:
    assert chunk_text("   ") == []


def test_embedding_text_includes_the_details() -> None:
    text = embedding_text("Dad fished.", ["Dad", "Tom"], "summer 1998", "Lake Erie")
    assert text == "Dad fished.. People: Dad, Tom. When: summer 1998. Where: Lake Erie"
    assert embedding_text("Dad fished.", [], None, None) == "Dad fished."


def test_parse_items_drops_malformed_items_and_cleans_the_rest() -> None:
    items = parse_items(
        {
            "memories": [
                {
                    "category": "event",
                    "content": "  Wedding day  ",
                    "people": [" Mum ", " "],
                    "confidence": 0.8,
                },
                {"category": "nonsense", "content": "x", "confidence": 0.8},
                {"category": "fact", "content": "", "confidence": 0.8},
                {"category": "fact", "content": "y", "confidence": 7},
                "not even an object",
            ]
        }
    )
    assert len(items) == 1
    assert items[0].content == "Wedding day"
    assert items[0].people == ["Mum"]


def test_parse_items_tolerates_a_wrong_shape() -> None:
    assert parse_items({"memories": "oops"}) == []
    assert parse_items({}) == []


def test_filter_items_drops_low_confidence_and_repeats() -> None:
    low = settings.MIN_EXTRACTION_CONFIDENCE - 0.01
    kept = filter_items(
        [
            item("Dad fished at the lake."),
            item("dad fished at the LAKE"),
            item("Unsure thing.", confidence=low),
        ]
    )
    assert [i.content for i in kept] == ["Dad fished at the lake."]


def _draft(content: str) -> ExtractedDraft:
    return ExtractedDraft(item=item(content), embedding=[0.0] * 768)


def _stored(db: Session, memory_id: object) -> dict[str, str]:
    db.expire_all()
    rows = db.exec(
        select(ExtractedMemory).where(col(ExtractedMemory.memory_id) == memory_id)
    ).all()
    return {row.content: row.status for row in rows}


def test_replace_extracted_keeps_edited_and_rejected_items(db: Session) -> None:
    memory = create_random_memory(db)
    replace_extracted(
        db,
        memory_id=memory.id,
        file_id=None,
        source=ExtractedSource.STORY,
        drafts=[_draft("Kept active."), _draft("Will be edited."), _draft("Rejected.")],
    )
    db.commit()
    for row in db.exec(
        select(ExtractedMemory).where(col(ExtractedMemory.memory_id) == memory.id)
    ).all():
        if row.content == "Will be edited.":
            row.status = ExtractedStatus.EDITED
        if row.content == "Rejected.":
            row.status = ExtractedStatus.REJECTED
        db.add(row)
    db.commit()

    added = replace_extracted(
        db,
        memory_id=memory.id,
        file_id=None,
        source=ExtractedSource.STORY,
        drafts=[_draft("Rejected."), _draft("Will be edited."), _draft("Brand new.")],
    )
    db.commit()

    assert added == 1
    assert _stored(db, memory.id) == {
        "Will be edited.": ExtractedStatus.EDITED,
        "Rejected.": ExtractedStatus.REJECTED,
        "Brand new.": ExtractedStatus.ACTIVE,
    }


def test_graph_extracts_from_a_story_without_reading_media(
    llm_client: FakeLLMClient,
) -> None:
    graph = build_extraction_graph(llm_client)

    result = graph.invoke({"person_name": "Dad", "text": "He fished. He sang."})

    drafts = drafts_from_state(result["drafts"])
    assert [d.item.content for d in drafts] == ["He fished.", "He sang."]
    assert all(len(d.embedding) == 768 for d in drafts)


def test_graph_reads_media_first(
    llm_client: FakeLLMClient, media_processor: FakeMediaProcessor
) -> None:
    graph = build_extraction_graph(llm_client, media_processor)

    result = graph.invoke({"person_name": "Nan", "path": "a.mp3", "kind": "audio"})

    assert result["text"] == media_processor.text
    assert media_processor.processed == [Path("a.mp3")]
    assert len(result["drafts"]) == 1


def test_graph_without_a_processor_cannot_read_media(
    llm_client: FakeLLMClient,
) -> None:
    graph = build_extraction_graph(llm_client)
    with pytest.raises(ValueError, match="media processor"):
        graph.invoke({"person_name": "Nan", "path": "a.mp3", "kind": "audio"})


def test_graph_skips_the_model_when_there_is_no_text(
    llm_client: FakeLLMClient,
) -> None:
    result = build_extraction_graph(llm_client).invoke(
        {"person_name": "Nan", "text": "  "}
    )

    assert "drafts" not in result
    assert llm_client.extract_prompts == []


def test_a_leftover_finished_run_does_not_bleed_into_the_next(
    llm_client: FakeLLMClient,
) -> None:
    thread_id = f"test-{uuid.uuid4()}"
    try:
        with open_checkpointer() as saver:
            graph = build_extraction_graph(llm_client, checkpointer=saver)
            first = run_extraction(
                graph, saver, {"person_name": "Nan", "text": "She sang."}, thread_id
            )
            # Same thread again, but this time there is nothing to extract: the
            # earlier drafts must not come back
            second = run_extraction(
                graph, saver, {"person_name": "Nan", "text": "  "}, thread_id
            )
    finally:
        clear_thread(thread_id)

    assert len(first["drafts"]) == 1
    assert "drafts" not in second
