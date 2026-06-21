"""DynamoDB implementation of the :class:`app.ports.repository.Repository` port.

Production persistence. Mirrors the SQLite adapter's behaviour over a single
DynamoDB table (``pk``/``sk``, no secondary indexes — matching the Terraform
``infra/modules/dynamodb`` table), so no domain code changes between backends.

Single-table layout
--------------------
======================  ==========================  ===============================
Item                    pk                          sk
======================  ==========================  ===============================
Counter (atomic ids)    ``COUNTER``                 ``<entity>``
Document                ``DOC``                     ``<id:010d>``
Title pointer           ``DOCTITLE``                ``<title>``
Document chunk          ``CHUNK``                   ``<doc_id:010d>#<ordinal:04d>``
Interaction             ``INT``                     ``<id:010d>``
Draft                   ``DRAFT``                   ``<id:010d>``
Ticket                  ``TICKET``                  ``<id:010d>``
Resolution              ``RES``                     ``<id:010d>``
======================  ==========================  ===============================

Numeric ids are zero-padded so the lexical sort key order equals numeric order;
``list_*`` reads use ``ScanIndexForward=False`` to return newest-first like the
SQLite ``ORDER BY id DESC``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.ports.repository import Chunk, CorpusItem
from app.schemas import (
    Document,
    Draft,
    GuardrailFinding,
    Resolution,
    Source,
    Ticket,
)

# Partition keys (entity collections).
_PK_DOC = "DOC"
_PK_DOCTITLE = "DOCTITLE"
_PK_CHUNK = "CHUNK"
_PK_INT = "INT"
_PK_DRAFT = "DRAFT"
_PK_TICKET = "TICKET"
_PK_RES = "RES"
_PK_COUNTER = "COUNTER"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sid(value: int) -> str:
    """Zero-padded id so the string sort key orders like the integer."""
    return f"{value:010d}"


def _int(value: Any) -> int:
    """DynamoDB returns numbers as ``Decimal``; collapse to ``int``."""
    return int(value) if value is not None else 0


class DynamoRepository:
    """Single-table DynamoDB store implementing the Repository port."""

    def __init__(self, table_name: str, *, region: str | None = None) -> None:
        resource = boto3.resource("dynamodb", region_name=region)
        self._table = resource.Table(table_name)

    # ── Lifecycle ────────────────────────────────────────────────────────────
    def init(self) -> None:
        """No-op: the table is provisioned by Terraform, not the application."""

    def reset(self) -> None:
        """Delete every item. Used by tests/dev — never call against prod data."""
        scan = self._table.scan(ProjectionExpression="pk, sk")
        items = list(scan.get("Items", []))
        while "LastEvaluatedKey" in scan:
            scan = self._table.scan(
                ProjectionExpression="pk, sk",
                ExclusiveStartKey=scan["LastEvaluatedKey"],
            )
            items.extend(scan.get("Items", []))
        with self._table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})

    # ── Id allocation ────────────────────────────────────────────────────────
    def _next_id(self, entity: str) -> int:
        resp = self._table.update_item(
            Key={"pk": _PK_COUNTER, "sk": entity},
            UpdateExpression="ADD seq :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return _int(resp["Attributes"]["seq"])

    # ── Documents + corpus ───────────────────────────────────────────────────
    def add_document(
        self,
        *,
        title: str,
        content: str,
        category: str,
        effective_date: str,
        chunks: list[Chunk],
    ) -> Document:
        doc_id = self._next_id("document")
        created = _now_iso()
        with self._table.batch_writer() as batch:
            batch.put_item(
                Item={
                    "pk": _PK_DOC,
                    "sk": _sid(doc_id),
                    "id": doc_id,
                    "title": title,
                    "category": category,
                    "effective_date": effective_date,
                    "content": content,
                    "created_at": created,
                }
            )
            batch.put_item(Item={"pk": _PK_DOCTITLE, "sk": title, "id": doc_id})
            for ch in chunks:
                batch.put_item(
                    Item={
                        "pk": _PK_CHUNK,
                        "sk": f"{_sid(doc_id)}#{ch.ordinal:04d}",
                        "doc_id": doc_id,
                        "title": title,
                        "ordinal": ch.ordinal,
                        "heading": ch.heading,
                        "context": ch.context,
                        "text": ch.text,
                        "char_start": ch.char_start,
                        "char_end": ch.char_end,
                    }
                )
        return Document(
            id=doc_id,
            title=title,
            category=category,
            effective_date=effective_date,
            created_at=created,
        )

    def get_document_by_title(self, title: str) -> Document | None:
        pointer = self._table.get_item(Key={"pk": _PK_DOCTITLE, "sk": title}).get("Item")
        if pointer is None:
            return None
        item = self._table.get_item(Key={"pk": _PK_DOC, "sk": _sid(_int(pointer["id"]))}).get(
            "Item"
        )
        return _to_document(item) if item else None

    def delete_document_by_title(self, title: str) -> bool:
        pointer = self._table.get_item(Key={"pk": _PK_DOCTITLE, "sk": title}).get("Item")
        if pointer is None:
            return False
        doc_id = _int(pointer["id"])
        chunks = self._table.query(
            KeyConditionExpression=Key("pk").eq(_PK_CHUNK)
            & Key("sk").begins_with(f"{_sid(doc_id)}#"),
            ProjectionExpression="pk, sk",
        ).get("Items", [])
        with self._table.batch_writer() as batch:
            batch.delete_item(Key={"pk": _PK_DOC, "sk": _sid(doc_id)})
            batch.delete_item(Key={"pk": _PK_DOCTITLE, "sk": title})
            for ch in chunks:
                batch.delete_item(Key={"pk": ch["pk"], "sk": ch["sk"]})
        return True

    def list_documents(self) -> list[Document]:
        items = self._table.query(
            KeyConditionExpression=Key("pk").eq(_PK_DOC),
            ScanIndexForward=False,
        ).get("Items", [])
        return [_to_document(i) for i in items]

    def count_documents(self) -> int:
        return _int(
            self._table.query(
                KeyConditionExpression=Key("pk").eq(_PK_DOC),
                Select="COUNT",
            ).get("Count", 0)
        )

    def corpus(self, *, interaction_limit: int = 200) -> list[CorpusItem]:
        items: list[CorpusItem] = []
        for ch in self._table.query(KeyConditionExpression=Key("pk").eq(_PK_CHUNK)).get(
            "Items", []
        ):
            items.append(
                CorpusItem(
                    title=str(ch["title"]),
                    snippet=str(ch["text"]),
                    index_text=f"{ch['context']} {ch['text']}",
                    kind="document",
                )
            )
        for row in self._table.query(
            KeyConditionExpression=Key("pk").eq(_PK_INT),
            ScanIndexForward=False,
            Limit=interaction_limit,
        ).get("Items", []):
            blob = f"{row['subject']} {row['body']}"
            items.append(
                CorpusItem(
                    title=f"{row['direction']} · {row['party']} · {row['subject']}",
                    snippet=blob,
                    index_text=blob,
                    kind="interaction",
                )
            )
        return items

    # ── Interactions ─────────────────────────────────────────────────────────
    def add_interaction(
        self,
        *,
        direction: str,
        party: str,
        subject: str,
        body: str,
        unit: str,
        case_ref: str,
        topic_key: str = "",
    ) -> int:
        interaction_id = self._next_id("interaction")
        self._table.put_item(
            Item={
                "pk": _PK_INT,
                "sk": _sid(interaction_id),
                "id": interaction_id,
                "direction": direction,
                "party": party,
                "subject": subject,
                "body": body,
                "unit": unit,
                "case_ref": case_ref,
                "topic_key": topic_key,
                "created_at": _now_iso(),
            }
        )
        return interaction_id

    # ── Drafts ───────────────────────────────────────────────────────────────
    def add_draft(
        self,
        *,
        interaction_id: int,
        intent: str,
        party: str,
        from_unit: str,
        unit: str,
        case_ref: str,
        priority: str,
        inbound_subject: str,
        inbound_snippet: str,
        body: str,
        auto_send_eligible: bool,
        findings: list[GuardrailFinding],
        sources: list[Source],
    ) -> int:
        draft_id = self._next_id("draft")
        self._table.put_item(
            Item={
                "pk": _PK_DRAFT,
                "sk": _sid(draft_id),
                "id": draft_id,
                "interaction_id": interaction_id,
                "intent": intent,
                "party": party,
                "from_unit": from_unit,
                "unit": unit,
                "case_ref": case_ref,
                "priority": priority,
                "inbound_subject": inbound_subject,
                "inbound_snippet": inbound_snippet,
                "body": body,
                "status": "pending",
                "auto_send_eligible": auto_send_eligible,
                "findings_json": json.dumps([f.model_dump() for f in findings]),
                "sources_json": json.dumps([s.model_dump() for s in sources]),
                "created_at": _now_iso(),
            }
        )
        return draft_id

    def get_draft(self, draft_id: int) -> Draft | None:
        item = self._table.get_item(Key={"pk": _PK_DRAFT, "sk": _sid(draft_id)}).get("Item")
        return _to_draft(item) if item else None

    def list_drafts(self, status: str | None = None) -> list[Draft]:
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("pk").eq(_PK_DRAFT),
            "ScanIndexForward": False,
        }
        if status:
            kwargs["FilterExpression"] = Attr("status").eq(status)
        items = self._table.query(**kwargs).get("Items", [])
        return [_to_draft(i) for i in items]

    def update_draft_body(
        self, draft_id: int, *, body: str, findings: list[GuardrailFinding]
    ) -> None:
        self._table.update_item(
            Key={"pk": _PK_DRAFT, "sk": _sid(draft_id)},
            UpdateExpression="SET body = :b, findings_json = :f",
            ExpressionAttributeValues={
                ":b": body,
                ":f": json.dumps([f.model_dump() for f in findings]),
            },
        )

    def set_draft_status(self, draft_id: int, status: str) -> None:
        self._table.update_item(
            Key={"pk": _PK_DRAFT, "sk": _sid(draft_id)},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status},
        )

    # ── Tickets ──────────────────────────────────────────────────────────────
    def add_ticket(
        self,
        *,
        title: str,
        type: str,
        priority: str,
        unit: str,
        case_ref: str,
        assignee: str,
        due_date: str = "",
        description: str = "",
        source: str = "email",
        source_interaction_id: int | None = None,
        source_resolution_id: int | None = None,
        topic_key: str = "",
    ) -> Ticket:
        ticket_id = self._next_id("ticket")
        created = _now_iso()
        item: dict[str, Any] = {
            "pk": _PK_TICKET,
            "sk": _sid(ticket_id),
            "id": ticket_id,
            "title": title,
            "type": type,
            "status": "todo",
            "priority": priority,
            "unit": unit,
            "case_ref": case_ref,
            "assignee": assignee,
            "due_date": due_date,
            "description": description,
            "source": source,
            "source_interaction_id": source_interaction_id,
            "source_resolution_id": source_resolution_id,
            "topic_key": topic_key,
            "created_at": created,
        }
        self._table.put_item(Item=item)
        return _to_ticket(item)

    def get_ticket(self, ticket_id: int) -> Ticket | None:
        item = self._table.get_item(Key={"pk": _PK_TICKET, "sk": _sid(ticket_id)}).get("Item")
        return _to_ticket(item) if item else None

    def list_tickets(self) -> list[Ticket]:
        items = self._table.query(
            KeyConditionExpression=Key("pk").eq(_PK_TICKET),
            ScanIndexForward=False,
        ).get("Items", [])
        return [_to_ticket(i) for i in items]

    def set_ticket_status(self, ticket_id: int, status: str) -> Ticket | None:
        existing = self._table.get_item(Key={"pk": _PK_TICKET, "sk": _sid(ticket_id)}).get("Item")
        if existing is None:
            return None
        updated = self._table.update_item(
            Key={"pk": _PK_TICKET, "sk": _sid(ticket_id)},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status},
            ReturnValues="ALL_NEW",
        ).get("Attributes")
        return _to_ticket(updated) if updated else None

    # ── Resolutions ──────────────────────────────────────────────────────────
    def add_resolution(
        self,
        *,
        title: str,
        effective_date: str,
        signed: bool,
        summary: str,
        keywords: str,
        unit: str = "",
    ) -> Resolution:
        res_id = self._next_id("resolution")
        self._table.put_item(
            Item={
                "pk": _PK_RES,
                "sk": _sid(res_id),
                "id": res_id,
                "title": title,
                "effective_date": effective_date,
                "signed": signed,
                "summary": summary,
                "keywords": keywords,
                "unit": unit,
            }
        )
        return Resolution(
            id=res_id,
            title=title,
            effective_date=effective_date,
            signed=signed,
            summary=summary,
            keywords=keywords,
            unit=unit,
        )

    def list_resolutions(self) -> list[Resolution]:
        items = self._table.query(
            KeyConditionExpression=Key("pk").eq(_PK_RES),
            ScanIndexForward=False,
        ).get("Items", [])
        return [_to_resolution(i) for i in items]

    def list_signed_resolutions(self) -> list[Resolution]:
        items = self._table.query(
            KeyConditionExpression=Key("pk").eq(_PK_RES),
            FilterExpression=Attr("signed").eq(True),
        ).get("Items", [])
        return [_to_resolution(i) for i in items]


# ── Item → schema mappers ────────────────────────────────────────────────────
def _to_document(item: dict[str, Any]) -> Document:
    return Document(
        id=_int(item["id"]),
        title=str(item["title"]),
        category=str(item["category"]),
        effective_date=str(item["effective_date"]),
        created_at=str(item["created_at"]),
    )


def _to_draft(item: dict[str, Any]) -> Draft:
    findings = [GuardrailFinding(**f) for f in json.loads(item["findings_json"])]
    sources = [Source(**s) for s in json.loads(item["sources_json"])]
    return Draft(
        id=_int(item["id"]),
        interaction_id=_int(item["interaction_id"]),
        intent=str(item["intent"]),
        party=str(item["party"]),
        from_unit=str(item["from_unit"]),
        unit=str(item["unit"]),
        case_ref=str(item["case_ref"]),
        priority=str(item["priority"]),
        inbound_subject=str(item["inbound_subject"]),
        inbound_snippet=str(item["inbound_snippet"]),
        body=str(item["body"]),
        status=str(item["status"]),  # type: ignore[arg-type]
        auto_send_eligible=bool(item["auto_send_eligible"]),
        findings=findings,
        sources=sources,
        created_at=str(item["created_at"]),
    )


def _to_ticket(item: dict[str, Any]) -> Ticket:
    sii = item.get("source_interaction_id")
    sri = item.get("source_resolution_id")
    return Ticket(
        id=_int(item["id"]),
        title=str(item["title"]),
        type=str(item["type"]),
        status=str(item["status"]),  # type: ignore[arg-type]
        priority=str(item["priority"]),
        unit=str(item["unit"]),
        case_ref=str(item["case_ref"]),
        assignee=str(item["assignee"]),
        source_interaction_id=_int(sii) if sii is not None else None,
        created_at=str(item["created_at"]),
        due_date=str(item["due_date"]),
        description=str(item["description"]),
        source=str(item["source"]),  # type: ignore[arg-type]
        source_resolution_id=_int(sri) if sri is not None else None,
        topic_key=str(item["topic_key"]),
    )


def _to_resolution(item: dict[str, Any]) -> Resolution:
    return Resolution(
        id=_int(item["id"]),
        title=str(item["title"]),
        effective_date=str(item["effective_date"]),
        signed=bool(item["signed"]),
        summary=str(item["summary"]),
        keywords=str(item["keywords"]),
        unit=str(item["unit"]),
    )
