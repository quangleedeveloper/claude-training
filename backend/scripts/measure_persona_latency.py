"""Measure how fast the local model starts and finishes a persona-sized reply.

Run on the demo machine: `uv run python scripts/measure_persona_latency.py [N]`.
Uses only the invented family in fixtures/ and never touches the database.
"""

import json
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.core.llm import ChatTurn, OllamaClient

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "families" / "thomas.json"
# Memory text must never leave the machine
LOCAL_HOSTS = {"localhost", "127.0.0.1", "ollama"}
QUESTIONS = [
    "Where was she born?",
    "What did she grow in the garden?",
    "How did she start working?",
    "What did she say about being tired?",
    "When did she get married?",
]
SYSTEM = (
    "You answer as the family remembers the person, using only the numbered "
    "memories and quotes below, and cite them as [n]. If they do not cover the "
    "question, say you do not know."
)


def build_prompt() -> tuple[str, list[ChatTurn]]:
    """A prompt of realistic size: 5 memories, 5 quotes and a 6-turn history."""
    family = json.loads(FIXTURE.read_text(encoding="utf-8"))
    items = [
        item
        for memory in family["memories"]
        for item in memory["items"]
        if item.get("confirmed") and item.get("status") != "rejected"
    ]
    facts = [i["content"] for i in items if i["category"] != "quote"][:5]
    quotes = [i["content"] for i in items if i["category"] == "quote"][:5]
    context = "Memories:\n" + "\n".join(f"[{n}] {t}" for n, t in enumerate(facts, 1))
    context += "\nQuotes:\n" + "\n".join(f'- "{q}"' for q in quotes)
    history = [
        ChatTurn("user" if n % 2 == 0 else "assistant", QUESTIONS[n % len(QUESTIONS)])
        for n in range(6)
    ]
    return f"{SYSTEM}\n\n{context}", history


def report(line: str) -> None:
    # A CLI report; ruff bans print() in app code
    sys.stdout.write(f"{line}\n")


def percentile(values: list[float], q: int) -> float:
    return statistics.quantiles(values, n=100, method="inclusive")[q - 1]


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    host = urlparse(settings.OLLAMA_BASE_URL).hostname
    if host not in LOCAL_HOSTS:
        report(f"Refusing to run: OLLAMA_BASE_URL host {host!r} is not local.")
        return 1

    client = OllamaClient(settings.OLLAMA_BASE_URL, settings.OLLAMA_TIMEOUT_SECONDS)
    system, history = build_prompt()
    first_chunk: list[float] = []
    total: list[float] = []
    for n in range(runs):
        turns = [*history, ChatTurn("user", QUESTIONS[n % len(QUESTIONS)])]
        started = time.perf_counter()
        first: float | None = None
        for _ in client.stream_answer(system, turns):
            if first is None:
                first = time.perf_counter() - started
        if first is None:
            report(f"Run {n + 1}: the model returned nothing.")
            return 1
        first_chunk.append(first)
        total.append(time.perf_counter() - started)
        report(f"Run {n + 1}/{runs}: first {first:.2f}s, total {total[-1]:.2f}s")

    report(f"\nModel: {settings.OLLAMA_CHAT_MODEL} · runs: {runs}")
    for label, values in (("first chunk", first_chunk), ("full reply", total)):
        report(
            f"{label}: p50 {percentile(values, 50):.2f}s, "
            f"p90 {percentile(values, 90):.2f}s"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
