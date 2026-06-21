"""Tests for the golden-set Agent Eval Gate harness (``eval/run_eval.py``).

These run as part of the standard ``python`` CI gate (pytest ``testpaths``
includes ``eval``) and keep the harness covered for the diff-cover gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.adapters.stub_llm import StubLLM

import run_eval
from run_eval import (
    CaseOutcome,
    EvalReport,
    build_corpus,
    evaluate_case,
    load_golden,
    main,
    run,
)


@pytest.fixture
def corpus():
    documents = load_golden()[0]["documents"]
    return build_corpus([dict(d) for d in documents])


@pytest.fixture
def llm() -> StubLLM:
    return StubLLM(accountable_human="Chairperson")


def test_real_golden_suite_passes() -> None:
    report = run()
    assert report.passed
    assert report.grounded_rate == 1.0
    assert report.fabricated_rate == 0.0
    assert report.fact_rate == 1.0


def test_answerable_case_is_grounded_with_fact(corpus, llm: StubLLM) -> None:
    case = {
        "id": "levy",
        "question": "How much is the monthly levy for 2025?",
        "answerable": True,
        "expected_sources": ["Levy Schedule 2025"],
        "expected_fact": "R1 850",
    }
    outcome = evaluate_case(case, corpus, llm)
    assert outcome.grounded is True
    assert outcome.fact_ok is True
    assert outcome.fabricated is False


def test_answerable_case_missing_source_is_ungrounded(corpus, llm: StubLLM) -> None:
    case = {
        "id": "wrong-source",
        "question": "What are the quiet hours?",
        "answerable": True,
        "expected_sources": ["Levy Schedule 2025"],
    }
    outcome = evaluate_case(case, corpus, llm)
    assert outcome.grounded is False
    assert "missing" in outcome.note


def test_unanswerable_case_refuses_cleanly(corpus, llm: StubLLM) -> None:
    case = {
        "id": "unknown",
        "question": "What is the wifi password for the clubhouse?",
        "answerable": False,
        "expected_sources": [],
    }
    outcome = evaluate_case(case, corpus, llm)
    assert outcome.grounded is None
    assert outcome.fabricated is False
    assert outcome.note == "refused"


def test_unanswerable_case_that_retrieves_is_flagged(corpus, llm: StubLLM) -> None:
    # Mislabelled case: a clearly answerable question marked unanswerable must
    # be caught as a leaked/fabricated citation, not silently passed.
    case = {
        "id": "leak",
        "question": "What are the quiet hours?",
        "answerable": False,
        "expected_sources": [],
    }
    outcome = evaluate_case(case, corpus, llm)
    assert outcome.fabricated is True
    assert outcome.note == "did not refuse cleanly"


def test_empty_report_has_neutral_rates() -> None:
    report = EvalReport(outcomes=[])
    assert report.grounded_rate == 1.0
    assert report.fabricated_rate == 0.0
    assert report.fact_rate == 1.0
    assert report.passed


def test_format_report_renders_pass_and_fail() -> None:
    passing = EvalReport(
        outcomes=[
            CaseOutcome("a", True, True, False, True, "ok"),
            CaseOutcome("b", False, None, False, None, "refused"),
        ]
    )
    text = run_eval._format_report(passing)
    assert "RESULT: PASS" in text
    assert "fact-ok" in text

    failing = EvalReport(outcomes=[CaseOutcome("c", True, False, True, False, "missing {'X'}")])
    failed_text = run_eval._format_report(failing)
    assert "RESULT: FAIL" in failed_text
    assert "UNGROUNDED" in failed_text


def test_load_golden_raises_when_empty(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_golden(tmp_path)


def test_main_passes_without_ci(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "Agent Eval Gate" in capsys.readouterr().out


def test_main_ci_passes_on_real_golden() -> None:
    assert main(["--ci"]) == 0


def test_main_ci_fails_on_regression(monkeypatch: pytest.MonkeyPatch) -> None:
    regression = EvalReport(outcomes=[CaseOutcome("bad", True, False, True, False, "regressed")])
    monkeypatch.setattr(run_eval, "run", lambda golden_dir=None: regression)
    assert main(["--ci"]) == 1


def test_golden_files_are_valid_json() -> None:
    golden = Path(run_eval.__file__).resolve().parent / "golden"
    for path in golden.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["documents"]
        assert data["cases"]
