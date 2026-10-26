import base64
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

import httpx
import ollama
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.core.config import settings
from app.core.prompt import DESCRIBE_IMAGE_PROMPT
from app.models import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """The language model could not be reached or returned something unusable."""


class LLMClient(Protocol):
    """Everything the AI features need from a model; tests use a fake of this."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def extract_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...

    def describe_image(self, path: Path) -> str: ...

    def answer(self, system: str, prompt: str) -> str: ...


class OllamaClient:
    """LangChain's Ollama integration against a local server; nothing leaves the
    machine. It is what the LangGraph nodes call, through `LLMClient`."""

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @contextmanager
    def _translate_errors(self) -> Iterator[None]:
        try:
            yield
        except ollama.ResponseError as exc:
            # Ollama explains a missing model ("try pulling it first") in the error
            raise LLMError(f"Ollama rejected the request: {exc.error}") from exc
        except (ConnectionError, httpx.HTTPError) as exc:
            raise LLMError(
                f"Could not reach Ollama at {self.base_url}: "
                f"{type(exc).__name__}. Is it running?"
            ) from exc

    def _chat(
        self,
        model: str,
        messages: list[BaseMessage],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        chat = ChatOllama(
            model=model,
            base_url=self.base_url,
            # Extraction should be repeatable, not creative
            temperature=0,
            format=response_format,
            client_kwargs={"timeout": self.timeout},
        )
        with self._translate_errors():
            reply = chat.invoke(messages)
        if not isinstance(reply.content, str):
            raise LLMError("Ollama returned no message content")
        return reply.content

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = OllamaEmbeddings(
            model=settings.OLLAMA_EMBED_MODEL,
            base_url=self.base_url,
            client_kwargs={"timeout": self.timeout},
        )
        with self._translate_errors():
            vectors = embeddings.embed_documents(texts)
        if len(vectors) != len(texts):
            raise LLMError("Ollama returned the wrong number of embeddings")
        if any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
            raise LLMError(
                f"Embedding model {settings.OLLAMA_EMBED_MODEL} must produce "
                f"{EMBEDDING_DIMENSIONS} dimensions"
            )
        return vectors

    def extract_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        content = self._chat(
            settings.OLLAMA_CHAT_MODEL,
            [SystemMessage(system), HumanMessage(prompt)],
            response_format=schema,
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("The model did not return valid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMError("The model did not return a JSON object")
        return parsed

    def describe_image(self, path: Path) -> str:
        image = base64.b64encode(path.read_bytes()).decode("ascii")
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": DESCRIBE_IMAGE_PROMPT,
                },
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image}"},
            ]
        )
        return self._chat(settings.OLLAMA_VISION_MODEL, [message]).strip()

    def answer(self, system: str, prompt: str) -> str:
        return self._chat(
            settings.OLLAMA_CHAT_MODEL,
            [SystemMessage(system), HumanMessage(prompt)],
        ).strip()


def get_llm_client() -> LLMClient:
    # Read settings per call so tests can change them
    return OllamaClient(settings.OLLAMA_BASE_URL, settings.OLLAMA_TIMEOUT_SECONDS)
