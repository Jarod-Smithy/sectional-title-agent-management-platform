"""Unit tests for the DynamoDB repository adapter.

Runs against ``moto``'s in-memory DynamoDB — no network, no AWS account — so the
production persistence seam is exercised in CI exactly like the SQLite one.
"""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from app.adapters.dynamo_repo import DynamoRepository
from app.ports.repository import Chunk
from app.schemas import GuardrailFinding, Source
from moto import mock_aws

TABLE = "stak-test-platform"
REGION = "af-south-1"


@pytest.fixture
def repo() -> Iterator[DynamoRepository]:
    with mock_aws():
        boto3.client("dynamodb", region_name=REGION).create_table(
            TableName=TABLE,
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        store = DynamoRepository(TABLE, region=REGION)
        store.init()
        yield store


def _chunks() -> list[Chunk]:
    return [
        Chunk(0, "Intro", "Levies are due monthly.", "Rules › Intro Levies", 0, 23),
        Chunk(1, "Pets", "No dogs over 10kg.", "Rules › Pets dogs", 24, 42),
    ]


# ── Documents + corpus ────────────────────────────────────────────────────────
def test_add_and_get_document(repo: DynamoRepository) -> None:
    doc = repo.add_document(
        title="House Rules",
        content="full text",
        category="rules",
        effective_date="2025-01-01",
        chunks=_chunks(),
    )
    assert doc.id == 1
    fetched = repo.get_document_by_title("House Rules")
    assert fetched is not None
    assert fetched.id == 1
    assert fetched.category == "rules"
    assert repo.get_document_by_title("Missing") is None


def test_list_and_count_documents_newest_first(repo: DynamoRepository) -> None:
    repo.add_document(title="A", content="x", category="rules", effective_date="", chunks=[])
    repo.add_document(title="B", content="y", category="rules", effective_date="", chunks=[])
    docs = repo.list_documents()
    assert [d.title for d in docs] == ["B", "A"]
    assert repo.count_documents() == 2


def test_delete_document_removes_chunks_and_pointer(repo: DynamoRepository) -> None:
    repo.add_document(
        title="House Rules",
        content="full text",
        category="rules",
        effective_date="",
        chunks=_chunks(),
    )
    assert repo.delete_document_by_title("House Rules") is True
    assert repo.get_document_by_title("House Rules") is None
    assert repo.count_documents() == 0
    # Chunks gone too — corpus has no document items.
    assert [c for c in repo.corpus() if c.kind == "document"] == []
    # Deleting a missing title is a no-op.
    assert repo.delete_document_by_title("House Rules") is False


def test_corpus_mixes_documents_and_interactions(repo: DynamoRepository) -> None:
    repo.add_document(
        title="House Rules",
        content="full text",
        category="rules",
        effective_date="",
        chunks=_chunks(),
    )
    repo.add_interaction(
        direction="inbound",
        party="owner@unit12",
        subject="Leaking pipe",
        body="Water in the ceiling.",
        unit="12",
        case_ref="CASE-1",
    )
    corpus = repo.corpus(interaction_limit=10)
    kinds = sorted({item.kind for item in corpus})
    assert kinds == ["document", "interaction"]
    assert any("Leaking pipe" in item.title for item in corpus)


# ── Drafts ────────────────────────────────────────────────────────────────────
def _add_draft(repo: DynamoRepository) -> int:
    interaction_id = repo.add_interaction(
        direction="inbound",
        party="owner@unit12",
        subject="Levy query",
        body="How much is the levy?",
        unit="12",
        case_ref="CASE-2",
    )
    return repo.add_draft(
        interaction_id=interaction_id,
        intent="reply",
        party="owner@unit12",
        from_unit="trustees",
        unit="12",
        case_ref="CASE-2",
        priority="normal",
        inbound_subject="Levy query",
        inbound_snippet="How much...",
        body="The monthly levy is R1500.",
        auto_send_eligible=True,
        findings=[GuardrailFinding(rule="tone", severity="info", message="ok")],
        sources=[Source(title="House Rules", snippet="Levies are due monthly.", kind="document")],
    )


def test_draft_lifecycle(repo: DynamoRepository) -> None:
    draft_id = _add_draft(repo)
    assert draft_id == 1
    draft = repo.get_draft(draft_id)
    assert draft is not None
    assert draft.status == "pending"
    assert draft.findings[0].rule == "tone"
    assert draft.sources[0].title == "House Rules"

    repo.update_draft_body(
        draft_id,
        body="Updated body.",
        findings=[GuardrailFinding(rule="length", severity="warn", message="short")],
    )
    repo.set_draft_status(draft_id, "filed")

    refreshed = repo.get_draft(draft_id)
    assert refreshed is not None
    assert refreshed.body == "Updated body."
    assert refreshed.status == "filed"
    assert refreshed.findings[0].rule == "length"

    assert [d.id for d in repo.list_drafts()] == [1]
    assert [d.id for d in repo.list_drafts(status="filed")] == [1]
    assert repo.list_drafts(status="pending") == []
    assert repo.get_draft(999) is None


# ── Tickets ───────────────────────────────────────────────────────────────────
def test_ticket_lifecycle(repo: DynamoRepository) -> None:
    ticket = repo.add_ticket(
        title="Fix lift",
        type="maintenance",
        priority="high",
        unit="common",
        case_ref="CASE-3",
        assignee="trustee@body",
        due_date="2025-02-01",
        description="Lift stuck on floor 3.",
        source="email",
        source_interaction_id=None,
    )
    assert ticket.id == 1
    assert ticket.status == "todo"

    got = repo.get_ticket(ticket.id)
    assert got is not None
    assert got.title == "Fix lift"

    updated = repo.set_ticket_status(ticket.id, "in_progress")
    assert updated is not None
    assert updated.status == "in_progress"

    assert [t.id for t in repo.list_tickets()] == [1]
    assert repo.get_ticket(404) is None
    assert repo.set_ticket_status(404, "done") is None


# ── Resolutions ───────────────────────────────────────────────────────────────
def test_resolution_register(repo: DynamoRepository) -> None:
    repo.add_resolution(
        title="Special Levy 2025",
        effective_date="2025-03-01",
        signed=True,
        summary="Approved a special levy.",
        keywords="levy special",
        unit="",
    )
    repo.add_resolution(
        title="Draft Pet Policy",
        effective_date="2025-04-01",
        signed=False,
        summary="Proposed pet rules.",
        keywords="pets",
    )
    assert [r.title for r in repo.list_resolutions()] == [
        "Draft Pet Policy",
        "Special Levy 2025",
    ]
    signed = repo.list_signed_resolutions()
    assert [r.title for r in signed] == ["Special Levy 2025"]


# ── Reset ─────────────────────────────────────────────────────────────────────
def test_reset_clears_all_items(repo: DynamoRepository) -> None:
    repo.add_document(
        title="House Rules",
        content="x",
        category="rules",
        effective_date="",
        chunks=_chunks(),
    )
    _add_draft(repo)
    repo.add_ticket(
        title="t",
        type="general",
        priority="normal",
        unit="",
        case_ref="",
        assignee="",
    )
    repo.reset()
    assert repo.count_documents() == 0
    assert repo.list_drafts() == []
    assert repo.list_tickets() == []
    assert repo.corpus() == []
    # Counters reset too — ids restart from 1.
    doc = repo.add_document(
        title="Fresh", content="x", category="rules", effective_date="", chunks=[]
    )
    assert doc.id == 1
