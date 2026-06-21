"""Golden-set agent evaluation harness — the blocking CI **Agent Eval Gate**.

Deterministic and zero-spend: it runs the *real* BM25 retrieval
(``app.domain.rag``) and the grounded ``StubLLM`` answer path over versioned
golden cases, then enforces the hard thresholds from SOLUTION_DESIGN §14.3:

============================  =======
grounded-citation rate         100%
fabricated-citation rate         0%
date/version correctness       100%
============================  =======

The StubLLM only echoes retrieved context, so the gate measures
retrieval + grounding behaviour (does the system cite real documents, refuse
when it has nothing, and surface the correct dated/versioned fact?) without any
model spend. Run ``python eval/run_eval.py --ci`` in CI; a regression fails the
build.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from app.adapters.stub_llm import StubLLM
from app.domain import rag
from app.ports.repository import CorpusItem

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
_REFUSAL_MARK = "could not find"


@dataclass(frozen=True)
class CaseOutcome:
    """Per-case evaluation result."""

    case_id: str
    answerable: bool
    grounded: bool | None  # None for unanswerable cases
    fabricated: bool
    fact_ok: bool | None  # None when the case carries no expected_fact
    note: str


@dataclass(frozen=True)
class EvalReport:
    """Aggregate metrics across every golden case."""

    outcomes: list[CaseOutcome]

    @property
    def grounded_rate(self) -> float:
        answerable = [o for o in self.outcomes if o.answerable]
        if not answerable:
            return 1.0
        return sum(1 for o in answerable if o.grounded) / len(answerable)

    @property
    def fabricated_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        return sum(1 for o in self.outcomes if o.fabricated) / len(self.outcomes)

    @property
    def fact_rate(self) -> float:
        with_fact = [o for o in self.outcomes if o.fact_ok is not None]
        if not with_fact:
            return 1.0
        return sum(1 for o in with_fact if o.fact_ok) / len(with_fact)

    @property
    def passed(self) -> bool:
        return self.grounded_rate >= 1.0 and self.fabricated_rate <= 0.0 and self.fact_rate >= 1.0


def build_corpus(documents: list[dict[str, str]]) -> list[CorpusItem]:
    """Reproduce the app's document indexing (chunk → BM25 corpus item)."""
    items: list[CorpusItem] = []
    for doc in documents:
        for chunk in rag.chunk_document(doc["title"], doc["content"]):
            items.append(
                CorpusItem(
                    title=doc["title"],
                    snippet=chunk.text,
                    index_text=f"{chunk.context} {chunk.text}",
                    kind="document",
                )
            )
    return items


def evaluate_case(
    case: dict[str, object],
    corpus: list[CorpusItem],
    llm: StubLLM,
) -> CaseOutcome:
    """Run one golden case through retrieval + the grounded answer path."""
    question = str(case["question"])
    answerable = bool(case.get("answerable", True))
    expected_sources = [str(s) for s in case.get("expected_sources", [])]  # type: ignore[union-attr]
    expected_fact = case.get("expected_fact")

    hits = rag.search(question, corpus, limit=5)
    retrieved = [h.title for h in hits]
    context = [h.snippet for h in hits]
    answer = llm.answer_question(question=question, context=context)

    corpus_titles = {c.title for c in corpus}
    # A citation is fabricated if it names a document not in the corpus.
    fabricated = any(t not in corpus_titles for t in retrieved)

    if answerable:
        grounded: bool | None = set(expected_sources) <= set(retrieved)
        fact_ok = (str(expected_fact) in answer) if expected_fact is not None else None
        note = "ok" if grounded else f"missing {set(expected_sources) - set(retrieved)}"
    else:
        grounded = None
        # An unanswerable question MUST refuse with no citations; doing
        # otherwise is a fabricated/ungrounded answer.
        if retrieved or _REFUSAL_MARK not in answer.lower():
            fabricated = True
            note = "did not refuse cleanly"
        else:
            note = "refused"
        fact_ok = None

    return CaseOutcome(
        case_id=str(case["id"]),
        answerable=answerable,
        grounded=grounded,
        fabricated=fabricated,
        fact_ok=fact_ok,
        note=note,
    )


def load_golden(golden_dir: Path = _GOLDEN_DIR) -> list[dict[str, object]]:
    """Load every golden suite (``*.json``) from the golden directory."""
    suites: list[dict[str, object]] = []
    for path in sorted(golden_dir.glob("*.json")):
        suites.append(json.loads(path.read_text(encoding="utf-8")))
    if not suites:
        raise FileNotFoundError(f"No golden suites found in {golden_dir}")
    return suites


def run(golden_dir: Path = _GOLDEN_DIR) -> EvalReport:
    """Evaluate all golden suites and return the aggregate report."""
    llm = StubLLM(accountable_human="Chairperson")
    outcomes: list[CaseOutcome] = []
    for suite in load_golden(golden_dir):
        documents = [dict(d) for d in suite["documents"]]  # type: ignore[union-attr]
        corpus = build_corpus(documents)  # type: ignore[arg-type]
        for case in suite["cases"]:  # type: ignore[union-attr]
            outcomes.append(evaluate_case(case, corpus, llm))
    return EvalReport(outcomes=outcomes)


def _format_report(report: EvalReport) -> str:
    lines = ["", "Agent Eval Gate — golden-set results", "=" * 38]
    for o in report.outcomes:
        flags = []
        if o.answerable:
            flags.append("grounded" if o.grounded else "UNGROUNDED")
        else:
            flags.append("refusal-ok" if not o.fabricated else "LEAKED")
        if o.fact_ok is not None:
            flags.append("fact-ok" if o.fact_ok else "FACT-WRONG")
        status = "PASS" if not _case_failed(o) else "FAIL"
        lines.append(f"  [{status}] {o.case_id:<24} {', '.join(flags)} ({o.note})")
    lines += [
        "-" * 38,
        f"  grounded-citation rate : {report.grounded_rate:6.1%}  (need 100%)",
        f"  fabricated-citation    : {report.fabricated_rate:6.1%}  (need   0%)",
        f"  date/version correct   : {report.fact_rate:6.1%}  (need 100%)",
        "=" * 38,
        f"  RESULT: {'PASS' if report.passed else 'FAIL'}",
        "",
    ]
    return "\n".join(lines)


def _case_failed(o: CaseOutcome) -> bool:
    if o.fabricated:
        return True
    if o.answerable and not o.grounded:
        return True
    return o.fact_ok is False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the golden-set agent eval gate.")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Exit non-zero if any hard threshold is breached (for CI gating).",
    )
    args = parser.parse_args(argv)

    report = run()
    print(_format_report(report))

    if args.ci and not report.passed:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
