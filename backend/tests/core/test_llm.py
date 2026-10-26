from pathlib import Path
from typing import Any

import httpx
import ollama
import pytest
from langchain_core.messages import AIMessage, BaseMessage

from app.core import llm as llm_module
from app.core.config import settings
from app.core.llm import LLMError, OllamaClient, get_llm_client
from app.models import EMBEDDING_DIMENSIONS

BASE = "http://ollama.test"


class Recorder:
    """What the fake LangChain classes were constructed and called with."""

    def __init__(self) -> None:
        self.chat_kwargs: dict[str, Any] = {}
        self.embedding_kwargs: dict[str, Any] = {}
        self.messages: list[BaseMessage] = []
        self.texts: list[str] = []


def fake_langchain(
    monkeypatch: pytest.MonkeyPatch,
    reply: Any = "ok",
    vectors: list[list[float]] | None = None,
    error: Exception | None = None,
) -> Recorder:
    recorder = Recorder()

    class FakeChatOllama:
        def __init__(self, **kwargs: Any) -> None:
            recorder.chat_kwargs = kwargs

        def invoke(self, messages: list[BaseMessage]) -> AIMessage:
            recorder.messages = messages
            if error is not None:
                raise error
            return AIMessage(content=reply)

    class FakeOllamaEmbeddings:
        def __init__(self, **kwargs: Any) -> None:
            recorder.embedding_kwargs = kwargs

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            recorder.texts = texts
            if error is not None:
                raise error
            return vectors if vectors is not None else []

    monkeypatch.setattr(llm_module, "ChatOllama", FakeChatOllama)
    monkeypatch.setattr(llm_module, "OllamaEmbeddings", FakeOllamaEmbeddings)
    return recorder


def client() -> OllamaClient:
    return OllamaClient(f"{BASE}/", timeout=5)


def test_embed_returns_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    vectors = [[0.1] * EMBEDDING_DIMENSIONS, [0.2] * EMBEDDING_DIMENSIONS]
    recorder = fake_langchain(monkeypatch, vectors=vectors)

    assert client().embed(["a", "b"]) == vectors
    assert recorder.texts == ["a", "b"]
    assert recorder.embedding_kwargs == {
        "model": settings.OLLAMA_EMBED_MODEL,
        "base_url": BASE,
        "client_kwargs": {"timeout": 5},
    }


def test_embed_of_nothing_does_not_call_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = fake_langchain(monkeypatch)
    assert client().embed([]) == []
    assert recorder.embedding_kwargs == {}


def test_embed_rejects_a_model_with_the_wrong_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_langchain(monkeypatch, vectors=[[0.1, 0.2]])
    with pytest.raises(LLMError, match="768 dimensions"):
        client().embed(["a"])


def test_embed_rejects_a_wrong_count(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_langchain(monkeypatch, vectors=[])
    with pytest.raises(LLMError, match="wrong number"):
        client().embed(["a"])


def test_extract_json_sends_the_schema_and_parses_the_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = fake_langchain(monkeypatch, reply='{"memories": []}')
    schema = {"type": "object"}

    assert client().extract_json("sys", "text", schema) == {"memories": []}
    assert recorder.chat_kwargs["format"] == schema
    assert recorder.chat_kwargs["temperature"] == 0
    assert recorder.chat_kwargs["model"] == settings.OLLAMA_CHAT_MODEL
    assert recorder.chat_kwargs["base_url"] == BASE
    assert [m.content for m in recorder.messages] == ["sys", "text"]


def test_extract_json_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_langchain(monkeypatch, reply="not json")
    with pytest.raises(LLMError, match="valid JSON"):
        client().extract_json("sys", "text", {})


def test_extract_json_rejects_a_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_langchain(monkeypatch, reply="[1, 2]")
    with pytest.raises(LLMError, match="JSON object"):
        client().extract_json("sys", "text", {})


def test_chat_without_text_content_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_langchain(monkeypatch, reply=[{"type": "image_url"}])
    with pytest.raises(LLMError, match="no message content"):
        client().answer("sys", "question")


def test_answer_strips_the_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_langchain(monkeypatch, reply="  Hello \n")
    assert client().answer("sys", "question") == "Hello"


def test_describe_image_sends_the_picture_to_the_vision_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorder = fake_langchain(monkeypatch, reply="A dog.")
    image = tmp_path / "dog.png"
    image.write_bytes(b"abc")

    assert client().describe_image(image) == "A dog."
    assert recorder.chat_kwargs["model"] == settings.OLLAMA_VISION_MODEL
    (message,) = recorder.messages
    assert isinstance(message.content, list)
    assert message.content[1] == {
        "type": "image_url",
        "image_url": "data:image/jpeg;base64,YWJj",
    }


def test_a_missing_model_surfaces_ollamas_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_langchain(
        monkeypatch,
        error=ollama.ResponseError("model 'x' not found, try pulling it", 404),
    )
    with pytest.raises(LLMError, match="try pulling it"):
        client().answer("sys", "question")


@pytest.mark.parametrize(
    "error", [ConnectionError("refused"), httpx.ConnectError("refused")]
)
def test_an_unreachable_server_says_so(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    fake_langchain(monkeypatch, error=error)
    with pytest.raises(LLMError, match="Could not reach Ollama at http://ollama.test"):
        client().answer("sys", "question")


def test_an_unreachable_server_also_fails_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_langchain(monkeypatch, error=ConnectionError("refused"))
    with pytest.raises(LLMError, match="Could not reach Ollama"):
        client().embed(["a"])


def test_get_llm_client_reads_the_settings() -> None:
    assert isinstance(get_llm_client(), OllamaClient)
