"""Domain models for the prototype (stdlib dataclasses — zero dependencies)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def to_dict(obj: Any) -> Any:
    """Recursively convert a dataclass (or list of them) to plain dict/list."""
    if isinstance(obj, list):
        return [to_dict(o) for o in obj]
    return asdict(obj)


@dataclass
class DocumentIn:
    title: str
    content: str
    category: str = "general"
    effective_date: str = ""


@dataclass
class Document:
    id: int
    title: str
    category: str
    effective_date: str
    created_at: str


@dataclass
class AskIn:
    question: str


@dataclass
class Source:
    title: str
    snippet: str
    kind: str  # "document" | "interaction"


@dataclass
class AskOut:
    answer: str
    sources: list[Source]


@dataclass
class EmailIn:
    sender: str
    subject: str
    body: str
    from_unit: str = ""  # the sender's own unit (the matter's "about" unit is parsed)


@dataclass
class GuardrailFinding:
    rule: str
    severity: str  # "block" | "warn" | "info"
    message: str


@dataclass
class Draft:
    id: int
    interaction_id: int
    intent: str
    party: str
    from_unit: str
    unit: str
    case_ref: str
    priority: str
    inbound_subject: str
    inbound_snippet: str
    body: str
    status: str  # "pending" | "filed" | "auto_filed" | "discarded"
    auto_send_eligible: bool
    findings: list[GuardrailFinding] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    created_at: str = ""


@dataclass
class Ticket:
    id: int
    title: str
    type: str
    status: str  # "todo" | "in_progress" | "done"
    priority: str
    unit: str
    case_ref: str
    assignee: str
    source_interaction_id: int | None
    created_at: str
    due_date: str = ""
    description: str = ""
    source: str = "email"  # 'email' | 'chair_email' | 'manual' | 'resolution'
    source_resolution_id: int | None = None
    topic_key: str = ""


@dataclass
class Resolution:
    id: int
    title: str
    effective_date: str
    signed: bool
    summary: str
    keywords: str
    unit: str = ""  # '' = scheme-wide


@dataclass
class Artifact:
    """A typed deliverable produced by a specialist agent for a task."""

    kind: str  # 'document' | 'research_brief' | 'action_plan' | 'correspondence' | 'calculation'
    title: str
    body: str
    specialist: str = ""
    sendable: bool = False  # correspondence the human may Send from the UI
    sent: bool = False  # set once the human clicks Send (prototype: simulated)
    code: str = ""  # code-interpreter source, when kind == 'calculation'
    result: str = ""  # computed result, when kind == 'calculation'
    tool_used: str = ""  # AgentCore capability used (e.g. 'code_interpreter', 'browser')


@dataclass
class ProposedTool:
    """A draft pull-request to promote a recurring throwaway tool into a
    permanent, governed MCP tool (reviewed by a human, merged via CI)."""

    reason: str
    branch: str
    pr_title: str
    pr_body: str
    file_path: str
    file_content: str
    simulated: bool = True  # prototype never actually pushes to GitHub


@dataclass
class AssistRun:
    id: int
    ticket_id: int
    status: str  # 'done' | 'blocked' | 'error'
    complexity: str
    model_tier: str
    model: str
    specialists: list[str]
    plan: list[str]
    artifacts: list[Artifact]
    findings: list[GuardrailFinding]
    capability_gaps: list[str]
    proposed_tool: ProposedTool | None
    cost_estimate: float
    summary: str
    created_at: str
