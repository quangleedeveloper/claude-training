import logging
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessageChunk, BaseMessage

from app.core import llm as llm_module
from app.core.config import settings
from app.core.llm import ChatTurn, LLMClient, LLMError, OllamaClient
from tests.utils.llm import FakeLLMClient

BASE = "http://ollama.test"
TURNS = [
    ChatTurn("user", "Where was she born?"),
    ChatTurn("assistant", "In Bristol [1]."),
    ChatTurn("user", "And her first job?"),
]


class StreamRecorder:
    def __init__(self) -> None:
        self.chat_kwargs: dict[str, Any] = {}
        self.messages: list[BaseMessage] = []


def fake_stream(
    monkeypatch: pytest.MonkeyPatch,
    chunks: list[Any],
    error: Exception | None = None,
    error_after: int | None = None,
) -> StreamRecorder:
    """Replace ChatOllama with one that streams `chunks`, failing with `error`
    before the first chunk, or after `error_after` chunks."""
    recorder = StreamRecorder()

    class FakeChatOllama:
        def __init__(self, **kwargs: Any) -> None:
            recorder.chat_kwargs = kwargs

        def stream(self, messages: list[BaseMessage]) -> Iterator[AIMessageChunk]:
            recorder.messages = messages
            if error is not None and error_after is None:
                raise error
            for index, chunk in enumerate(chunks):
                if error is not None and index == error_after:
                    raise error
                yield AIMessageChunk(content=chunk)

    monkeypatch.setattr(llm_module, "ChatOllama", FakeChatOllama)
    return recorder


def client() -> OllamaClient:
    return OllamaClient(f"{BASE}/", timeout=5)


def test_stream_answer_fake_and_protocol() -> None:
    llm: LLMClient = FakeLLMClient()
    assert isinstance(llm, FakeLLMClient)

    assert list(llm.stream_answer("sys", TURNS)) == [
        "Fake ",
        "answer ",
        "citing [1].",
    ]
    assert llm.stream_calls == [("sys", TURNS)]


def test_the_fake_counts_a_call_even_if_the_stream_is_not_read() -> None:
    llm = FakeLLMClient()
    llm.stream_answer("sys", TURNS)
    assert len(llm.stream_calls) == 1


def test_the_fake_streams_chosen_chunks() -> None:
    llm = FakeLLMClient()
    llm.stream_chunks = ["a", "b"]
    assert list(llm.stream_answer("sys", [])) == ["a", "b"]


def test_stream_error_before_first_chunk() -> None:
    llm = FakeLLMClient()
    llm.error = "down"
    with pytest.raises(LLMError, match="down"):
        llm.stream_answer("sys", TURNS)
    assert llm.stream_calls == []


def test_the_fake_can_fail_midway() -> None:
    llm = FakeLLMClient()
    llm.error_after = 1
    seen: list[str] = []
    with pytest.raises(LLMError):
        for chunk in llm.stream_answer("sys", TURNS):
            seen.append(chunk)
    assert seen == ["Fake "]


def test_ollama_streams_non_empty_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = fake_stream(monkeypatch, ["Hi ", "", "lo"])

    assert list(client().stream_answer("sys", TURNS)) == ["Hi ", "lo"]
    assert recorder.chat_kwargs["model"] == settings.OLLAMA_CHAT_MODEL
    assert recorder.chat_kwargs["base_url"] == BASE
    assert recorder.chat_kwargs["temperature"] == 0
    assert recorder.chat_kwargs["client_kwargs"] == {"timeout": 5}
    assert [(m.type, m.content) for m in recorder.messages] == [
        ("system", "sys"),
        ("human", "Where was she born?"),
        ("ai", "In Bristol [1]."),
        ("human", "And her first job?"),
    ]


def test_ollama_stream_without_text_content_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_stream(monkeypatch, [[{"type": "image_url"}]])
    with pytest.raises(LLMError, match="no message content"):
        list(client().stream_answer("sys", TURNS))


def test_ollama_stream_error_before_first_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_stream(monkeypatch, ["x"], error=ConnectionError("refused"))
    with pytest.raises(LLMError, match="The AI service is unavailable"):
        list(client().stream_answer("sys", TURNS))


def test_stream_error_mid_reply_is_generic(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake_stream(
        monkeypatch,
        ["Hi ", "lo"],
        error=httpx.ReadError("secret story text"),
        error_after=1,
    )
    seen: list[str] = []
    with caplog.at_level(logging.ERROR, logger="app.core.llm"):
        with pytest.raises(LLMError) as raised:
            for chunk in client().stream_answer("sys", TURNS):
                seen.append(chunk)

    assert seen == ["Hi "]
    assert str(raised.value) == "The AI service is unavailable. Is Ollama running?"
    assert "secret story text" not in caplog.text
    assert BASE not in str(raised.value)
