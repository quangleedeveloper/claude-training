"""Check the grounding eval cases and the family fixtures without any model.

Run from the repo root or from backend/: `uv run python scripts/validate_evals.py`.
Exits 1 and lists every problem it finds, so it can run on GitHub's runners for any
change to `evals/`, `fixtures/`, `qa/` or the spec.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CASE_FIELDS = ("id", "from", "fixture", "question", "expect")
CASE_ID = re.compile(r"^G-\d+$")
AC_ID = re.compile(r"AC-N?\d+\.\d+")
# "from" may also be an incident id (every production incident adds a case)
INCIDENT_ID = re.compile(r"^INC-\d+$")
# Fixture emails must be on a reserved domain so nothing can ever reach a real person
SAFE_EMAIL_SUFFIXES = (".test", "@example.com", "@example.org", "@example.net")


def load_json(path: Path, problems: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"{path.name}: cannot be read as JSON ({type(exc).__name__})")
        return None
    if not isinstance(data, dict):
        problems.append(f"{path.name}: must be a JSON object")
        return None
    return data


def fixture_ids(fixture: dict[str, Any]) -> set[str]:
    return {
        item["id"]
        for memory in fixture.get("memories", [])
        for item in memory.get("items", [])
        if isinstance(item, dict) and "id" in item
    }


def validate_fixture(path: Path, fixture: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    name = path.name
    if not fixture.get("_note"):
        problems.append(f"{name}: needs a `_note` saying the family is invented")
    for key in ("users", "persons", "memories"):
        if not fixture.get(key):
            problems.append(f"{name}: `{key}` is missing or empty")
    for user in fixture.get("users", []):
        email = str(user.get("email", ""))
        if not email.endswith(SAFE_EMAIL_SUFFIXES):
            problems.append(f"{name}: user email {email!r} is not on a reserved domain")
    if "backend/uploads" in path.read_text(encoding="utf-8").replace("\\", "/"):
        problems.append(
            f"{name}: must not point into backend/uploads (real family media)"
        )
    person_keys = {p.get("key") for p in fixture.get("persons", [])}
    seen: set[str] = set()
    for memory in fixture.get("memories", []):
        if memory.get("person") not in person_keys:
            problems.append(f"{name}: memory {memory.get('id')} has an unknown person")
        for item in memory.get("items", []):
            item_id = item.get("id")
            if item_id in seen:
                problems.append(f"{name}: item id {item_id} is used twice")
            seen.add(str(item_id))
    return problems


def validate_case(
    path: Path,
    case: dict[str, Any],
    fixtures: dict[str, dict[str, Any]],
    spec_acs: set[str],
    matrix_text: str,
) -> list[str]:
    problems: list[str] = []
    name = path.name
    for field in REQUIRED_CASE_FIELDS:
        if field not in case:
            problems.append(f"{name}: missing `{field}`")
    if problems:
        return problems
    if not CASE_ID.match(str(case["id"])):
        problems.append(f"{name}: id {case['id']!r} must look like G-123")
    if path.stem != case["id"]:
        problems.append(f"{name}: file name must match the id {case['id']!r}")
    origin = str(case["from"])
    if not (INCIDENT_ID.match(origin) or origin in spec_acs):
        problems.append(f"{name}: `from` {origin!r} is not an AC in the spec")
    fixture = fixtures.get(str(case["fixture"]))
    if fixture is None:
        problems.append(f"{name}: fixture {case['fixture']!r} does not exist")
        return problems
    ids = fixture_ids(fixture)
    expect = case["expect"]
    if not isinstance(expect, dict):
        return [*problems, f"{name}: `expect` must be an object"]
    for key in ("cites", "not_cites"):
        for item_id in expect.get(key, []):
            if item_id not in ids:
                problems.append(
                    f"{name}: `{key}` names {item_id!r}, not in the fixture"
                )
    if "person" in case and case["person"] not in {
        p.get("key") for p in fixture.get("persons", [])
    }:
        problems.append(f"{name}: person {case['person']!r} is not in the fixture")
    if "as" in case and case["as"] not in {
        u.get("key") for u in fixture.get("users", [])
    }:
        problems.append(f"{name}: `as` {case['as']!r} is not a fixture user")
    if "fallback" in expect and not isinstance(expect["fallback"], bool):
        problems.append(f"{name}: `expect.fallback` must be true or false")
    if expect.get("fallback") is True and expect.get("cites"):
        problems.append(f"{name}: a no-memory reply cannot cite anything")
    if f"{case['id']}.json" not in matrix_text:
        problems.append(f"{name}: not referenced by any row of qa/test-matrix.md")
    return problems


def validate(root: Path = REPO_ROOT) -> list[str]:
    """Every problem found in the cases and fixtures under `root`."""
    problems: list[str] = []
    spec = (root / "specs/persona-conversation/spec.md").read_text(encoding="utf-8")
    spec_acs = set(AC_ID.findall(spec))
    matrix = (root / "qa/test-matrix.md").read_text(encoding="utf-8")

    fixtures: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "fixtures/families").glob("*.json")):
        fixture = load_json(path, problems)
        if fixture is not None:
            fixtures[path.relative_to(root).as_posix()] = fixture
            problems.extend(validate_fixture(path, fixture))

    case_files = sorted((root / "evals/grounding").glob("G-*.json"))
    if not case_files:
        problems.append("evals/grounding: no cases found")
    ids: set[str] = set()
    for path in case_files:
        case = load_json(path, problems)
        if case is None:
            continue
        if case.get("id") in ids:
            problems.append(f"{path.name}: id {case.get('id')!r} is used twice")
        ids.add(str(case.get("id")))
        problems.extend(validate_case(path, case, fixtures, spec_acs, matrix))
    return problems


def report(line: str) -> None:
    # A CLI report; ruff bans print() in app code
    sys.stdout.write(f"{line}\n")


def main() -> int:
    problems = validate()
    if problems:
        report(f"{len(problems)} problem(s) in the grounding evals:")
        for problem in problems:
            report(f"- {problem}")
        return 1
    report("The grounding eval cases and fixtures are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
