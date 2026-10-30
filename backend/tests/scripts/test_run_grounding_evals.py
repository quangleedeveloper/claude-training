import json
from pathlib import Path

import pytest
from sqlmodel import Session, col, func, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.core.prompt import PERSONA_NO_MEMORY
from app.models import ExtractedMemory, Memory, PersonMember
from tests.scripts.test_validate_evals import load_script
from tests.utils.llm import FakeLLMClient

runner = load_script("run_grounding_evals")

MINI = {
    "_note": "Invented family for the runner's own tests.",
    "family": "mini",
    "users": [
        {"key": "owner", "email": "owner@mini-family.test", "role": "owner"},
        {"key": "member", "email": "member@mini-family.test", "role": "member"},
    ],
    "persons": [{"key": "gran", "name": "Grace Mini", "other_names": ["Gran"]}],
    "memories": [
        {
            "id": "M-01",
            "person": "gran",
            "title": "Baking",
            "story": "Gran baked bread on Sundays.",
            "items": [
                {
                    "id": "I-01",
                    "category": "fact",
                    "content": "Grace baked bread on Sundays",
                    "confirmed": True,
                },
                {
                    "id": "I-02",
                    "category": "fact",
                    "content": "Grace sailed a boat in Whitby",
                    "confirmed": False,
                },
                {
                    "id": "I-03",
                    "category": "fact",
                    "content": "Grace was born in Bristol",
                    "confirmed": True,
                    "was_edited": True,
                },
            ],
        }
    ],
}


def mini_case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "id": "G-901",
        "from": "AC-5.1",
        "fixture": "fixtures/families/mini.json",
        "person": "gran",
        "as": "member",
        "question": "Grace baked bread on Sundays",
        "expect": {
            "fallback": False,
            "cites": ["I-01"],
            "not_cites": ["I-02"],
            "must_include": ["fake answer"],
            "must_not_include": [],
        },
    }
    case.update(overrides)
    return case


@pytest.fixture
def mini_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo-shaped folder holding the mini family and one case."""
    (tmp_path / "fixtures/families").mkdir(parents=True)
    (tmp_path / "fixtures/families/mini.json").write_text(
        json.dumps(MINI), encoding="utf-8"
    )
    (tmp_path / "evals/grounding").mkdir(parents=True)
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "CASES_DIR", tmp_path / "evals/grounding")
    monkeypatch.setattr(settings, "AI_BACKEND", "fake")
    return tmp_path


def write_case(root: Path, case: dict[str, object]) -> None:
    (root / "evals/grounding" / f"{case['id']}.json").write_text(
        json.dumps(case), encoding="utf-8"
    )


def count_accounts(emails: list[str]) -> int:
    with Session(engine) as session:
        return session.exec(
            select(func.count())
            .select_from(runner.User)
            .where(col(runner.User.email).in_(emails))
        ).one()


# --- scoring -----------------------------------------------------------------


def score(expect: dict[str, object], **kwargs: object) -> object:
    defaults: dict[str, object] = {
        "text": "A reply.",
        "fallback": False,
        "source_ids": [],
        "unknown_sources": 0,
    }
    defaults.update(kwargs)
    return runner.score_run(expect, **defaults)  # type: ignore[arg-type]


def test_a_matching_reply_passes() -> None:
    result = score(
        {"fallback": False, "cites": ["I-01"], "must_include": ["bread"]},
        text="She baked Bread [1].",
        source_ids=["I-01"],
    )
    assert result.ok and result.invented == []  # type: ignore[attr-defined]


def test_fixed_no_memory_reply_is_checked_exactly() -> None:
    expect = {"fallback": True, "cites": []}
    good = score(expect, text=PERSONA_NO_MEMORY, fallback=True)
    wrong_text = score(expect, text="I am not sure.", fallback=True)
    with_sources = score(
        expect, text=PERSONA_NO_MEMORY, fallback=True, source_ids=["I-01"]
    )
    answered = score(expect, text="She baked bread.", fallback=False)

    assert good.ok  # type: ignore[attr-defined]
    assert not wrong_text.ok  # type: ignore[attr-defined]
    assert not with_sources.ok  # type: ignore[attr-defined]
    assert not answered.ok  # type: ignore[attr-defined]


def test_an_answer_is_expected_when_fallback_is_false() -> None:
    result = score({"fallback": False}, text=PERSONA_NO_MEMORY, fallback=True)
    assert result.failures == [  # type: ignore[attr-defined]
        "answered with the no-memory reply, expected an answer"
    ]


def test_an_omitted_fallback_accepts_either_outcome() -> None:
    assert score({}, text=PERSONA_NO_MEMORY, fallback=True).ok  # type: ignore[attr-defined]
    assert score({}, text="Some answer", fallback=False).ok  # type: ignore[attr-defined]


def test_cites_and_not_cites_use_the_sources() -> None:
    result = score(
        {"cites": ["I-01"], "not_cites": ["I-02"]}, source_ids=["I-02", "I-03"]
    )
    assert result.failures == [  # type: ignore[attr-defined]
        "did not cite I-01",
        "cited I-02, which it must not",
    ]
    assert result.invented == []  # type: ignore[attr-defined]


def test_must_not_include_is_an_invented_memory_and_case_insensitive() -> None:
    result = score({"must_not_include": ["Violin"]}, text="She played the VIOLIN.")
    assert result.invented == ["said 'Violin'"]  # type: ignore[attr-defined]
    assert not result.ok  # type: ignore[attr-defined]


def test_a_source_outside_the_fixture_is_an_invented_memory() -> None:
    result = score({}, unknown_sources=2)
    assert result.invented == ["2 cited source(s) are not in the fixture"]  # type: ignore[attr-defined]


def test_missing_phrases_fail_without_inventing() -> None:
    result = score({"must_include": ["basil"]})
    assert result.failures == ["missing 'basil'"]  # type: ignore[attr-defined]
    assert result.invented == []  # type: ignore[attr-defined]


# --- judging, report -------------------------------------------------------------


def run(ok: bool = True, invented: bool = False, seconds: float = 1.0) -> object:
    return runner.RunScore(
        failures=[] if ok else ["x"],
        invented=["said 'x'"] if invented else [],
        seconds=seconds,
    )


def test_one_run_must_pass() -> None:
    case = {"id": "G-1", "from": "AC-1.1"}
    assert runner.judge_case(case, [run()]).passed
    assert not runner.judge_case(case, [run(ok=False)]).passed


def test_three_runs_need_two_good_ones_and_flag_flakiness() -> None:
    case = {"id": "G-1", "from": "AC-1.1"}
    two_of_three = runner.judge_case(case, [run(), run(), run(ok=False)])
    one_of_three = runner.judge_case(case, [run(), run(ok=False), run(ok=False)])

    assert two_of_three.passed and two_of_three.flaky
    assert not one_of_three.passed


def test_one_invented_memory_in_any_run_fails_the_case() -> None:
    case = {"id": "G-1", "from": "AC-1.1"}
    result = runner.judge_case(case, [run(), run(), run(ok=False, invented=True)])
    assert not result.passed
    assert result.invented == 1


def test_percentile() -> None:
    assert runner.percentile([], 90) == 0.0
    assert runner.percentile([5.0], 50) == 5.0
    assert (
        runner.percentile([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], 90)
        == 9.0
    )
    assert runner.percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.0


def test_report_and_markdown_gate() -> None:
    results = [
        runner.judge_case({"id": "G-1", "from": "AC-1.1"}, [run(seconds=2.0)]),
        runner.judge_case(
            {"id": "G-2", "from": "AC-2.1"}, [run(ok=False, invented=True)]
        ),
    ]

    report = runner.build_report(results, repeats=1)
    markdown = runner.render_markdown(report, 0.5)

    assert report["cases"] == 2 and report["passed"] == 1
    assert report["pass_rate"] == 0.5
    assert report["invented_memories"] == 1
    assert report["results"][1]["id"] == "G-2"
    assert "**FAIL**" in markdown
    assert "| G-2 | AC-2.1 | FAIL | 1 |" in markdown
    assert runner.gate_failed(report, 0.5) is True
    clean = runner.build_report(results[:1], repeats=1)
    assert runner.gate_failed(clean, 0.9) is False
    assert "**pass**" in runner.render_markdown(clean, 0.9)


def test_parse_events() -> None:
    body = (
        'event: token\ndata: {"text": "Hi "}\n\n'
        'event: token\ndata: {"text": "there"}\n\n'
        'event: done\ndata: {"sources": [], "fallback": true}\n\n'
    )

    events = runner.parse_events(body)

    assert [name for name, _ in events] == ["token", "token", "done"]
    assert events[2][1]["fallback"] is True


# --- seeding and running ----------------------------------------------------------------


def test_refuses_to_touch_real_looking_accounts() -> None:
    with pytest.raises(SystemExit):
        runner.check_safe_email("someone@gmail.com")
    runner.check_safe_email("owner@thomas-family.test")


@pytest.mark.usefixtures("mini_repo")
def test_seed_fixture_builds_the_family_and_cleans_up(
    llm_client: FakeLLMClient,
) -> None:
    emails = [u["email"] for u in MINI["users"]]  # type: ignore[index]
    try:
        seeded = runner.seed_fixture(MINI, llm_client)

        assert set(seeded.person_ids) == {"gran"}
        assert sorted(seeded.item_ids.values()) == ["I-01", "I-02", "I-03"]
        with Session(engine) as session:
            members = session.exec(
                select(PersonMember).where(
                    col(PersonMember.person_id) == seeded.person_ids["gran"]
                )
            ).all()
            assert [m.user_id for m in members] == [seeded.user_ids["member"]]
            items = {
                seeded.item_ids[i.id]: i
                for i in session.exec(select(ExtractedMemory)).all()
                if i.id in seeded.item_ids
            }
            assert items["I-01"].confirmed_at is not None
            assert items["I-02"].confirmed_at is None
            assert items["I-03"].was_edited is True
            memory = session.get(Memory, items["I-01"].memory_id)
            assert memory is not None and memory.person_name == "Grace Mini"
            owner = crud.get_user_by_email(session=session, email=emails[0])
            assert owner is not None and memory.owner_id == owner.id
    finally:
        runner.remove_accounts(emails)

    assert count_accounts(emails) == 0


@pytest.mark.usefixtures("mini_repo")
def test_seeding_twice_replaces_leftovers(llm_client: FakeLLMClient) -> None:
    emails = [u["email"] for u in MINI["users"]]  # type: ignore[index]
    try:
        runner.seed_fixture(MINI, llm_client)
        seeded = runner.seed_fixture(MINI, llm_client)
        assert len(seeded.item_ids) == 3
        assert count_accounts(emails) == 2
    finally:
        runner.remove_accounts(emails)


def test_main_runs_a_passing_case_end_to_end(
    mini_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_case(mini_repo, mini_case())
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    emails = [u["email"] for u in MINI["users"]]  # type: ignore[index]

    code = runner.main(
        ["--json", str(json_path), "--markdown", str(markdown_path), "--repeats", "2"]
    )

    assert code == 0, capsys.readouterr().out
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["passed"] == 1 and report["repeats"] == 2
    assert report["results"][0]["runs"][0]["sources"] == ["I-01"]
    assert "**pass**" in markdown_path.read_text(encoding="utf-8")
    assert count_accounts(emails) == 0


def test_main_fails_on_an_invented_memory_and_still_cleans_up(
    mini_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case = mini_case()
    case["expect"] = {"must_not_include": ["fake answer"]}
    write_case(mini_repo, case)
    emails = [u["email"] for u in MINI["users"]]  # type: ignore[index]

    code = runner.main(["--min-pass-rate", "0"])

    assert code == 1
    assert "1 invented memories" in capsys.readouterr().out
    assert count_accounts(emails) == 0


def test_main_reports_a_case_that_got_no_answer(mini_repo: Path) -> None:
    write_case(mini_repo, mini_case())
    # An unrelated question finds nothing, so the persona gives the fixed reply
    case = mini_case(question="Completely unrelated zebra", id="G-902")
    write_case(mini_repo, case)

    code = runner.main(["--cases", "G-902", "--min-pass-rate", "0.5"])

    assert code == 1  # the case wants a cited answer, but only the fixed reply came


def test_unknown_case_ids_are_refused(mini_repo: Path) -> None:
    write_case(mini_repo, mini_case())

    with pytest.raises(SystemExit):
        runner.main(["--cases", "G-999"])


@pytest.mark.usefixtures("mini_repo")
def test_repeats_must_be_positive() -> None:
    with pytest.raises(SystemExit):
        runner.main(["--repeats", "0"])
