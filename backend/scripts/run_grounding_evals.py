"""Run the grounding eval cases against the real local model and report the result.

    uv run python scripts/run_grounding_evals.py [--repeats 3] [--cases G-101,G-110]
        [--min-pass-rate 0.9] [--json report.json] [--markdown report.md]

It seeds each case's fixture family into the configured database, drives the cases
through the real conversation API (login, open, send, read the stream), scores them,
and removes everything it created, even when it fails. Use a throwaway database: the
runner only deletes accounts whose email is on a reserved test domain, but it does
write and delete rows.

An *invented memory* (spec AC-N7.1) is a `must_not_include` hit, or a cited source
that is not in the case's fixture. Any of them fails the run. Latency here is the time
of a whole turn through the test client and is informational: the pass/fail check for
speed is a manual run on the demo machine (`measure_persona_latency.py`).
"""

import argparse
import json
import logging
import math
import os
import secrets
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.core.llm import LLMClient, LLMError, get_llm_client
from app.core.prompt import PERSONA_NO_MEMORY
from app.core.security import get_password_hash
from app.main import app
from app.models import (
    ConversationSummary,
    ExtractedMemory,
    ExtractedSource,
    ExtractedStatus,
    Memory,
    Person,
    PersonCreate,
    PersonMember,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = REPO_ROOT / "evals" / "grounding"
# The runner only ever deletes accounts on these (the fixture validator enforces them)
SAFE_EMAIL_SUFFIXES = (".test", "@example.com", "@example.org", "@example.net")
DEFAULT_MIN_PASS_RATE = 0.9
API = settings.API_V1_STR


@dataclass
class RunScore:
    """One run of one case: what failed, and which failures count as inventing."""

    failures: list[str] = field(default_factory=list)
    invented: list[str] = field(default_factory=list)
    seconds: float = 0.0
    text: str = ""
    source_ids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass
class CaseResult:
    id: str
    origin: str
    runs: list[RunScore]
    passed: bool
    invented: int
    flaky: bool


def score_run(
    expect: dict[str, Any],
    *,
    text: str,
    fallback: bool,
    source_ids: list[str],
    unknown_sources: int,
) -> RunScore:
    """Score one reply against a case's `expect` block (rules: evals/grounding/README)."""
    score = RunScore(text=text, source_ids=source_ids)
    lowered = text.lower()

    wanted_fallback = expect.get("fallback")
    if wanted_fallback is True:
        if not fallback or text.strip() != PERSONA_NO_MEMORY or source_ids:
            score.failures.append("expected the fixed no-memory reply with no sources")
    elif wanted_fallback is False and fallback:
        score.failures.append("answered with the no-memory reply, expected an answer")

    for item_id in expect.get("cites", []):
        if item_id not in source_ids:
            score.failures.append(f"did not cite {item_id}")
    for item_id in expect.get("not_cites", []):
        if item_id in source_ids:
            score.failures.append(f"cited {item_id}, which it must not")
    for phrase in expect.get("must_include", []):
        if phrase.lower() not in lowered:
            score.failures.append(f"missing {phrase!r}")
    for phrase in expect.get("must_not_include", []):
        if phrase.lower() in lowered:
            score.failures.append(f"said {phrase!r}, which it must not")
            score.invented.append(f"said {phrase!r}")
    if unknown_sources:
        message = f"{unknown_sources} cited source(s) are not in the fixture"
        score.failures.append(message)
        score.invented.append(message)
    return score


def judge_case(case: dict[str, Any], runs: list[RunScore]) -> CaseResult:
    """A case passes when no run invented anything and at least 2 in 3 runs met every
    other check (all of them when it ran once)."""
    invented = sum(len(run.invented) for run in runs)
    good = sum(1 for run in runs if run.ok)
    needed = len(runs) if len(runs) == 1 else math.ceil(len(runs) * 2 / 3)
    return CaseResult(
        id=case["id"],
        origin=case["from"],
        runs=runs,
        passed=invented == 0 and good >= needed,
        invented=invented,
        flaky=0 < good < len(runs),
    )


def percentile(values: list[float], q: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * q / 100) - 1)]


def build_report(results: list[CaseResult], repeats: int) -> dict[str, Any]:
    seconds = [run.seconds for result in results for run in result.runs]
    passed = sum(1 for result in results if result.passed)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "chat_model": settings.OLLAMA_CHAT_MODEL,
        "embed_model": settings.OLLAMA_EMBED_MODEL,
        "ai_backend": settings.AI_BACKEND,
        "repeats": repeats,
        "cases": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "invented_memories": sum(result.invented for result in results),
        "flaky": [result.id for result in results if result.flaky],
        # Open, earlier turns and the question through the test client, informational
        "turn_seconds_p50": round(percentile(seconds, 50), 2),
        "turn_seconds_p90": round(percentile(seconds, 90), 2),
        "results": [
            {
                "id": result.id,
                "from": result.origin,
                "passed": result.passed,
                "invented": result.invented,
                "flaky": result.flaky,
                "runs": [
                    {
                        "ok": run.ok,
                        "failures": run.failures,
                        "seconds": round(run.seconds, 2),
                        "sources": run.source_ids,
                        "reply": run.text,
                    }
                    for run in result.runs
                ],
            }
            for result in results
        ],
    }


def render_markdown(report: dict[str, Any], min_pass_rate: float) -> str:
    gate = (
        "FAIL"
        if report["invented_memories"] or report["pass_rate"] < min_pass_rate
        else "pass"
    )
    lines = [
        "## Persona grounding evals",
        "",
        f"**{gate}** · {report['passed']}/{report['cases']} cases "
        f"({report['pass_rate']:.0%}, needs {min_pass_rate:.0%}) · "
        f"**{report['invented_memories']} invented memories** (must be 0) · "
        f"{report['repeats']} run(s) per case",
        "",
        f"Model `{report['chat_model']}` (embeddings `{report['embed_model']}`, "
        f"backend `{report['ai_backend']}`). Time of a whole case (open, earlier turns, question) p50 "
        f"{report['turn_seconds_p50']} s, p90 {report['turn_seconds_p90']} s "
        "(informational: the speed check is the manual run on the demo machine).",
        "",
        "| Case | Protects | Result | Invented | What failed |",
        "|------|----------|--------|----------|-------------|",
    ]
    for item in report["results"]:
        failures = sorted({f for run in item["runs"] for f in run["failures"]})
        flaky = " (flaky)" if item["flaky"] else ""
        lines.append(
            f"| {item['id']} | {item['from']} | "
            f"{'pass' if item['passed'] else 'FAIL'}{flaky} | {item['invented']} | "
            f"{'; '.join(failures) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def parse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """The `event:` / `data:` blocks of one streamed reply."""
    events = []
    for block in body.replace("\r\n", "\n").strip().split("\n\n"):
        name, data = "", ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if name:
            events.append((name, json.loads(data or "{}")))
    return events


@dataclass
class Seeded:
    """What a fixture became in the database."""

    passwords: dict[str, str]
    emails: dict[str, str]
    person_ids: dict[str, uuid.UUID]
    item_ids: dict[uuid.UUID, str]
    user_ids: dict[str, uuid.UUID]


def check_safe_email(email: str) -> None:
    if not email.endswith(SAFE_EMAIL_SUFFIXES):
        raise SystemExit(f"Refusing to touch {email!r}: not on a reserved test domain")


def remove_accounts(emails: list[str]) -> None:
    for email in emails:
        check_safe_email(email)
    with Session(engine) as session:
        for email in emails:
            user = crud.get_user_by_email(session=session, email=email)
            if user is not None:
                session.delete(user)
        session.commit()


def seed_fixture(fixture: dict[str, Any], llm: LLMClient) -> Seeded:
    """Create the fixture's users, persons, memberships, memories and items.

    Items keep the state the fixture gives them (`confirmed`, `was_edited`, `status`),
    with embeddings from the configured model, so the persona sees what a family's
    own review would have produced."""
    emails = {u["key"]: u["email"] for u in fixture["users"]}
    remove_accounts(list(emails.values()))
    passwords = {key: secrets.token_urlsafe(16) for key in emails}
    seeded = Seeded(passwords, emails, {}, {}, {})

    with Session(engine) as session:
        users: dict[str, User] = {}
        for user in fixture["users"]:
            # Built directly: `UserCreate` refuses the reserved `.test` domain the
            # fixture uses on purpose, so no email can reach a real person
            row = User(
                email=user["email"],
                hashed_password=get_password_hash(passwords[user["key"]]),
                is_active=True,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            users[user["key"]] = row
        owner = users["owner"]
        persons: dict[str, Person] = {}
        for person in fixture["persons"]:
            persons[person["key"]] = crud.create_person(
                session=session,
                person_in=PersonCreate(
                    name=person["name"], other_names=person.get("other_names", [])
                ),
                owner_id=owner.id,
            )
        for user in fixture["users"]:
            if user.get("role") == "member":
                for person in persons.values():
                    session.add(
                        PersonMember(
                            person_id=person.id,
                            user_id=users[user["key"]].id,
                            adult_confirmed=True,
                        )
                    )
        session.commit()

        for memory in fixture["memories"]:
            person = persons[memory["person"]]
            story = Memory(
                title=memory["title"],
                person_name=person.name,
                content=memory["story"],
                owner_id=owner.id,
                person_id=person.id,
            )
            session.add(story)
            session.commit()
            vectors = llm.embed([item["content"] for item in memory["items"]])
            for item, vector in zip(memory["items"], vectors, strict=True):
                extracted = ExtractedMemory(
                    memory_id=story.id,
                    category=item["category"],
                    content=item["content"],
                    event_date_text=item.get("event_date_text"),
                    confidence=item.get("confidence", 0.9),
                    status=item.get(
                        "status",
                        ExtractedStatus.EDITED
                        if item.get("was_edited")
                        else ExtractedStatus.ACTIVE,
                    ),
                    source=ExtractedSource.STORY,
                    embedding=vector,
                    was_edited=bool(item.get("was_edited")),
                    confirmed_at=datetime.now(UTC) if item.get("confirmed") else None,
                )
                session.add(extracted)
                session.commit()
                seeded.item_ids[extracted.id] = item["id"]
        seeded.person_ids = {key: person.id for key, person in persons.items()}
        seeded.user_ids = {key: user.id for key, user in users.items()}
    return seeded


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def send(
    client: TestClient, headers: dict[str, str], conversation_id: str, text: str
) -> list[tuple[str, dict[str, Any]]]:
    response = client.post(
        f"{API}/conversations/{conversation_id}/messages",
        headers=headers,
        json={"text": text},
    )
    response.raise_for_status()
    return parse_events(response.text)


def run_case_once(client: TestClient, case: dict[str, Any], seeded: Seeded) -> RunScore:
    """One fresh conversation: the summary and earlier turns, then the question."""
    user_key = case.get("as", "member")
    person_key = case.get("person", "mai")
    person_id = seeded.person_ids[person_key]
    user_id = seeded.user_ids[user_key]
    headers = login(client, seeded.emails[user_key], seeded.passwords[user_key])

    with Session(engine) as session:
        for old in session.exec(
            select(ConversationSummary).where(
                col(ConversationSummary.person_id) == person_id,
                col(ConversationSummary.user_id) == user_id,
            )
        ).all():
            session.delete(old)
        if case.get("summary"):
            session.add(
                ConversationSummary(
                    person_id=person_id, user_id=user_id, content=case["summary"]
                )
            )
        session.commit()

    started = time.perf_counter()
    opened = client.post(f"{API}/persons/{person_id}/conversations", headers=headers)
    opened.raise_for_status()
    conversation_id = opened.json()["conversation_id"]
    for earlier in case.get("turns_before", []):
        send(client, headers, conversation_id, earlier)
    events = send(client, headers, conversation_id, case["question"])
    seconds = time.perf_counter() - started

    text = "".join(data["text"] for name, data in events if name == "token")
    done = next((data for name, data in events if name == "done"), None)
    if done is None:
        return RunScore(
            failures=["the reply ended with an error and no answer"],
            seconds=seconds,
            text=text,
        )
    source_ids: list[str] = []
    unknown = 0
    for source in done["sources"]:
        fixture_id = seeded.item_ids.get(uuid.UUID(source["item"]["id"]))
        if fixture_id is None:
            unknown += 1
        else:
            source_ids.append(fixture_id)
    score = score_run(
        case["expect"],
        text=text,
        fallback=bool(done["fallback"]),
        source_ids=source_ids,
        unknown_sources=unknown,
    )
    score.seconds = seconds
    return score


def run_case(client: TestClient, case: dict[str, Any], seeded: Seeded) -> RunScore:
    """`run_case_once`, but an error from the API fails this case instead of the run."""
    try:
        return run_case_once(client, case, seeded)
    except httpx.HTTPStatusError as exc:
        return RunScore(
            failures=[f"the API answered {exc.response.status_code}"],
        )
    except KeyError as exc:
        return RunScore(failures=[f"the fixture has no {exc.args[0]!r}"])


def load_cases(only: set[str] | None) -> list[dict[str, Any]]:
    cases = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CASES_DIR.glob("G-*.json"))
    ]
    if only:
        unknown = only - {case["id"] for case in cases}
        if unknown:
            raise SystemExit(f"Unknown case id(s): {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case["id"] in only]
    return cases


def run_cases(
    cases: list[dict[str, Any]], repeats: int, llm: LLMClient
) -> list[CaseResult]:
    results: list[CaseResult] = []
    # The idle sweep would call the real model on its own
    settings.CONVERSATION_SWEEP_SECONDS = 0
    fixtures: dict[str, dict[str, Any]] = {}
    seeded_by_fixture: dict[str, Seeded] = {}
    try:
        with TestClient(app) as client:
            for case in cases:
                key = case["fixture"]
                if key not in seeded_by_fixture:
                    fixtures[key] = json.loads(
                        (REPO_ROOT / key).read_text(encoding="utf-8")
                    )
                    seeded_by_fixture[key] = seed_fixture(fixtures[key], llm)
                runs = [
                    run_case(client, case, seeded_by_fixture[key])
                    for _ in range(repeats)
                ]
                results.append(judge_case(case, runs))
                report_progress(results[-1])
    finally:
        for fixture in fixtures.values():
            remove_accounts([u["email"] for u in fixture["users"]])
    return results


def report(line: str) -> None:
    # A CLI report; ruff bans print() in app code
    sys.stdout.write(f"{line}\n")


def report_progress(result: CaseResult) -> None:
    flaky = " (flaky)" if result.flaky else ""
    report(f"{result.id}: {'pass' if result.passed else 'FAIL'}{flaky}")


def gate_failed(summary: dict[str, Any], min_pass_rate: float) -> bool:
    return bool(summary["invented_memories"]) or summary["pass_rate"] < min_pass_rate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--repeats", type=int, default=int(os.environ.get("EVAL_REPEATS", 1))
    )
    parser.add_argument("--cases", help="comma-separated case ids; default all")
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=float(os.environ.get("EVAL_MIN_PASS_RATE", DEFAULT_MIN_PASS_RATE)),
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        default=os.environ.get("EVAL_REPORT_ONLY", "").lower() in ("1", "true"),
        help="exit 0 even when the gate would fail; a crash or a missing model "
        "(exit 2) still fails",
    )
    parser.add_argument("--json", type=Path, help="write the full report here")
    parser.add_argument("--markdown", type=Path, help="write the summary here")
    args = parser.parse_args(argv)
    # The app and the HTTP libraries log every request; the report is the output
    logging.getLogger().setLevel(logging.WARNING)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    only = set(args.cases.split(",")) if args.cases else None
    llm = get_llm_client()
    try:
        results = run_cases(load_cases(only), args.repeats, llm)
    except LLMError as exc:
        report(f"The model is not available: {exc}")
        return 2

    summary = build_report(results, args.repeats)
    markdown = render_markdown(summary, args.min_pass_rate)
    report(markdown)
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(markdown, encoding="utf-8")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write(markdown)
    if gate_failed(summary, args.min_pass_rate) and not args.report_only:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
