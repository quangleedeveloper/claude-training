import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, BACKEND / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_evals = load_script("validate_evals")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A copy of the parts of the repo the validator reads, safe to break."""
    root = tmp_path / "repo"
    shutil.copytree(REPO / "evals", root / "evals")
    shutil.copytree(REPO / "fixtures", root / "fixtures")
    (root / "specs/persona-conversation").mkdir(parents=True)
    shutil.copy(
        REPO / "specs/persona-conversation/spec.md",
        root / "specs/persona-conversation/spec.md",
    )
    (root / "qa").mkdir()
    shutil.copy(REPO / "qa/test-matrix.md", root / "qa/test-matrix.md")
    return root


def case_path(root: Path, case_id: str = "G-101") -> Path:
    return root / "evals/grounding" / f"{case_id}.json"


def edit_case(root: Path, case_id: str, change: dict[str, object]) -> None:
    path = case_path(root, case_id)
    case = json.loads(path.read_text(encoding="utf-8"))
    case.update(change)
    path.write_text(json.dumps(case), encoding="utf-8")


def test_the_repo_is_valid() -> None:
    assert validate_evals.validate(REPO) == []


def test_a_copy_of_the_repo_is_valid(repo: Path) -> None:
    assert validate_evals.validate(repo) == []


def test_a_case_that_is_not_json(repo: Path) -> None:
    case_path(repo).write_text("{not json", encoding="utf-8")

    problems = validate_evals.validate(repo)

    assert any("G-101.json" in p and "JSON" in p for p in problems)


def test_a_case_with_missing_fields(repo: Path) -> None:
    case_path(repo).write_text(json.dumps({"id": "G-101"}), encoding="utf-8")

    problems = validate_evals.validate(repo)

    assert "G-101.json: missing `from`" in problems
    assert "G-101.json: missing `expect`" in problems


def test_from_must_be_an_ac_in_the_spec(repo: Path) -> None:
    edit_case(repo, "G-101", {"from": "AC-99.9"})

    assert any("not an AC in the spec" in p for p in validate_evals.validate(repo))


def test_from_may_be_an_incident_id(repo: Path) -> None:
    edit_case(repo, "G-101", {"from": "INC-7"})

    assert validate_evals.validate(repo) == []


def test_cited_ids_must_exist_in_the_fixture(repo: Path) -> None:
    case = json.loads(case_path(repo).read_text(encoding="utf-8"))
    case["expect"]["cites"] = ["I-99"]
    case["expect"]["not_cites"] = ["I-98"]
    case_path(repo).write_text(json.dumps(case), encoding="utf-8")

    problems = validate_evals.validate(repo)

    assert any("`cites` names 'I-99'" in p for p in problems)
    assert any("`not_cites` names 'I-98'" in p for p in problems)


def test_unknown_person_user_and_fixture(repo: Path) -> None:
    edit_case(repo, "G-101", {"person": "nobody", "as": "ghost"})
    edit_case(repo, "G-102", {"fixture": "fixtures/families/missing.json"})

    problems = validate_evals.validate(repo)

    assert any("person 'nobody'" in p for p in problems)
    assert any("`as` 'ghost'" in p for p in problems)
    assert any("does not exist" in p for p in problems)


def test_a_no_memory_case_cannot_cite(repo: Path) -> None:
    case = json.loads(case_path(repo, "G-102").read_text(encoding="utf-8"))
    case["expect"]["cites"] = ["I-01"]
    case_path(repo, "G-102").write_text(json.dumps(case), encoding="utf-8")

    assert any("cannot cite" in p for p in validate_evals.validate(repo))


def test_a_case_must_be_in_the_test_matrix(repo: Path) -> None:
    matrix = repo / "qa/test-matrix.md"
    matrix.write_text(
        matrix.read_text(encoding="utf-8").replace("G-117.json", "G-1xx.json"),
        encoding="utf-8",
    )

    assert any(
        "G-117.json" in p and "test-matrix" in p for p in validate_evals.validate(repo)
    )


def test_file_name_must_match_the_id(repo: Path) -> None:
    edit_case(repo, "G-101", {"id": "G-555"})

    assert any("file name must match" in p for p in validate_evals.validate(repo))


def test_duplicate_ids_are_found(repo: Path) -> None:
    shutil.copy(case_path(repo, "G-101"), repo / "evals/grounding/G-901.json")
    edit_case(repo, "G-901", {"id": "G-101"})

    assert any("used twice" in p for p in validate_evals.validate(repo))


def test_fixture_must_be_marked_invented_and_use_reserved_emails(repo: Path) -> None:
    path = repo / "fixtures/families/thomas.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    del fixture["_note"]
    fixture["users"][0]["email"] = "someone@gmail.com"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    problems = validate_evals.validate(repo)

    assert any("`_note`" in p for p in problems)
    assert any("reserved domain" in p for p in problems)


def test_fixture_must_not_point_into_real_uploads(repo: Path) -> None:
    path = repo / "fixtures/families/thomas.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    fixture["memories"][0]["photo"] = "backend/uploads/real-family/photo.jpg"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    assert any("backend/uploads" in p for p in validate_evals.validate(repo))


def test_duplicate_item_ids_in_a_fixture(repo: Path) -> None:
    path = repo / "fixtures/families/thomas.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    fixture["memories"][1]["items"][0]["id"] = fixture["memories"][0]["items"][0]["id"]
    path.write_text(json.dumps(fixture), encoding="utf-8")

    assert any("is used twice" in p for p in validate_evals.validate(repo))


def test_main_exit_codes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(validate_evals, "validate", lambda: [])
    assert validate_evals.main() == 0
    assert "valid" in capsys.readouterr().out

    monkeypatch.setattr(validate_evals, "validate", lambda: ["G-1.json: broken"])
    assert validate_evals.main() == 1
    assert "- G-1.json: broken" in capsys.readouterr().out
