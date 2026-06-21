"""Unit tests for the pure domain logic (no I/O)."""

from __future__ import annotations

from app.domain import guardrails, intake, rag, threads
from app.ports.repository import CorpusItem
from app.schemas import Resolution


def _resolution(keywords: str, *, unit: str = "", signed: bool = True) -> Resolution:
    return Resolution(
        id=1,
        title="Test resolution",
        effective_date="2025-01-01",
        signed=signed,
        summary="",
        keywords=keywords,
        unit=unit,
    )


# ── Guardrails ────────────────────────────────────────────────────────────────
def test_screen_blocks_interest_without_resolution() -> None:
    findings = guardrails.screen("We will charge interest on the arrears.", "Unit 3", [])
    assert guardrails.has_block(findings)
    assert any(f.rule.startswith("resolution-gate") for f in findings)


def test_screen_clears_interest_with_signed_scheme_resolution() -> None:
    signed = [_resolution("interest penalty", unit="")]
    findings = guardrails.screen("We will charge interest on the arrears.", "Unit 3", signed)
    assert not guardrails.has_block(findings)


def test_screen_unit_scoped_resolution_does_not_cover_other_unit() -> None:
    signed = [_resolution("interest", unit="Unit 14")]
    findings = guardrails.screen("We will charge interest on the arrears.", "Unit 3", signed)
    assert guardrails.has_block(findings)


def test_screen_no_go_disconnect_utilities() -> None:
    findings = guardrails.screen("We will disconnect the water supply.", "", [])
    assert guardrails.has_block(findings)
    assert any(f.rule == "no-go" for f in findings)


def test_screen_defamation_warns() -> None:
    findings = guardrails.screen("The contractor was negligent.", "", [])
    assert any(f.severity == "warn" for f in findings)
    assert not guardrails.has_block(findings)


def test_screen_clean_text_has_no_findings() -> None:
    findings = guardrails.screen("Thank you for your email, noted.", "", [])
    assert findings == []


# ── Intake ────────────────────────────────────────────────────────────────────
def test_classify_intent_maintenance() -> None:
    assert intake.classify_intent("Geyser leak", "There is a leak in unit 4") == "maintenance"


def test_classify_intent_general_when_unmatched() -> None:
    assert intake.classify_intent("xyz", "qpr") == "general"


def test_extract_party_and_unit() -> None:
    assert intake.extract_party("jane.doe@example.com") == "Jane Doe"
    assert intake.extract_unit("Re: Unit 12 leak", "") == "Unit 12"
    assert intake.extract_unit("hello", "") == ""


def test_priority_high() -> None:
    assert intake.priority("URGENT flooding", "") == "high"
    assert intake.priority("routine query", "") == "normal"


def test_case_ref_shape() -> None:
    # Default path: wall clock + random suffix (exercises the production seams).
    ref = intake.case_ref("maintenance", "Unit 7")
    assert ref.startswith("MAI-7-")


def test_case_ref_is_deterministic_when_seams_injected() -> None:
    from datetime import UTC, datetime

    fixed = datetime(2026, 6, 21, 9, 30, 0, tzinfo=UTC)
    ref1 = intake.case_ref("complaint", "Unit 12", now=fixed, token_factory=lambda: "abcd")
    ref2 = intake.case_ref("complaint", "Unit 12", now=fixed, token_factory=lambda: "abcd")
    assert ref1 == ref2  # same seams -> fully reproducible
    assert ref1.startswith("COM-12-")
    assert ref1.endswith("-ABCD")
    # Fallbacks: short intent -> GEN, no unit digits -> SCH (scheme-wide).
    scheme = intake.case_ref("", "common area", now=fixed, token_factory=lambda: "ef01")
    assert scheme.startswith("GEN-SCH-")
    assert scheme.endswith("-EF01")


def test_is_task_email() -> None:
    chairs = {"chair@acaciaheights.co.za"}
    assert intake.is_task_email("chair@acaciaheights.co.za", "TASK: fix gate", chairs)
    assert not intake.is_task_email("owner@x.com", "TASK: fix gate", chairs)
    assert not intake.is_task_email("chair@acaciaheights.co.za", "just a note", chairs)


def test_task_title_and_due_date() -> None:
    assert intake.task_title_from_subject("TASK: Repair the pool") == "Repair the pool"
    assert intake.task_title_from_subject("TASK:") == "Untitled task"
    assert intake.extract_due_date("Please action by 2025-06-30 thanks") == "2025-06-30"
    assert intake.extract_due_date("no date here") == ""


# ── Threads ───────────────────────────────────────────────────────────────────
def test_normalize_subject_strips_prefixes() -> None:
    assert threads.normalize_subject("Re: Fwd: Garden") == "garden"


def test_topic_key_groups_same_matter() -> None:
    a = threads.topic_key_for_text("Garden maintenance", "", "Jane", "Unit 3")
    b = threads.topic_key_for_text("Re: Garden maintenance", "", "Jane", "Unit 3")
    assert a == b
    assert a.startswith("unit3:")


def test_topic_key_falls_back_to_body() -> None:
    key = threads.topic_key_for_text("", "broken gate motor at entrance", "", "")
    assert key.startswith("scheme:")


# ── RAG ───────────────────────────────────────────────────────────────────────
def test_tokenize_drops_stopwords() -> None:
    assert "the" not in rag.tokenize("the garden")
    assert "garden" in rag.tokenize("the garden")


def test_chunk_document_splits_long_content() -> None:
    body = "Rules:\n\n" + ("All owners must keep the garden tidy. " * 60)
    chunks = rag.chunk_document("House Rules", body)
    assert len(chunks) >= 2
    assert chunks[0].context.startswith("House Rules")


def test_chunk_document_empty() -> None:
    assert rag.chunk_document("Title", "   ") == []


def test_search_ranks_relevant_item_first() -> None:
    corpus = [
        CorpusItem(
            title="Garden",
            snippet="garden upkeep",
            index_text="garden maintenance upkeep",
            kind="document",
        ),
        CorpusItem(
            title="Parking",
            snippet="parking bays",
            index_text="parking bays allocation",
            kind="document",
        ),
    ]
    hits = rag.search("garden maintenance", corpus, limit=5)
    assert hits
    assert hits[0].title == "Garden"


def test_search_empty_query_or_corpus() -> None:
    assert rag.search("   ", [], limit=5) == []
    assert rag.search("garden", [], limit=5) == []
