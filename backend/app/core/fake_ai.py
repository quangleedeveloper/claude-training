"""Deterministic stand-ins for the AI models.

Used by the tests and by the end-to-end run (`AI_BACKEND=fake`), where there is no
Ollama or Whisper. The fakes never read the files they are given and invent no
knowledge: they echo back simple, predictable text so the whole flow can be driven.
"""

import hashlib
import math
import re
from pathlib import Path
from typing import Any

from app.core.llm import LLMError
from app.models import EMBEDDING_DIMENSIONS


def fake_embedding(text: str) -> list[float]:
    """Bag-of-words vector: texts sharing words are close, unrelated ones are not.

    Deterministic, so search ordering can be asserted without a real model.
    """
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        index = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        vector[index % EMBEDDING_DIMENSIONS] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class FakeLLMClient:
    """Stands in for Ollama. Set `error` to simulate it being down, or `extracted`
    to control exactly what the model "extracts"."""

    def __init__(self) -> None:
        self.error: str | None = None
        self.extracted: list[dict[str, Any]] | None = None
        self.extract_prompts: list[str] = []
        self.answer_prompts: list[str] = []

    def _check(self) -> None:
        if self.error is not None:
            raise LLMError(self.error)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._check()
        return [fake_embedding(text) for text in texts]

    def extract_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        self._check()
        self.extract_prompts.append(prompt)
        if self.extracted is not None:
            return {"memories": self.extracted}
        # One fact per sentence, which is enough to follow the data end to end
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", prompt) if s.strip()]
        return {
            "memories": [
                {"category": "fact", "content": s, "confidence": 0.9} for s in sentences
            ]
        }

    def describe_image(self, path: Path) -> str:
        self._check()
        return "A photo of the family having a picnic by the lake."

    def answer(self, system: str, prompt: str) -> str:
        self._check()
        self.answer_prompts.append(prompt)
        return "Fake answer citing [1]."


class FakeTranscriber:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def transcribe(self, path: Path) -> str:
        self.paths.append(path)
        return "Grandpa told us about the old farm."
