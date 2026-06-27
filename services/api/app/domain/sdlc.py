"""SDLC domain — shape runtime signals into issue-tracker content.

Pure functions (no I/O): they turn a captured client-side error into a concise,
de-duplicating issue title + a structured Markdown body. The route layer hands
the result to the :class:`app.ports.sdlc.IssueTracker`.
"""

from __future__ import annotations

_MAX_TITLE = 110
_MAX_FIELD = 4000


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_bug_report(
    *,
    message: str,
    stack: str = "",
    url: str = "",
    user_agent: str = "",
    context: str = "",
) -> tuple[str, str]:
    """Return ``(title, body)`` for a captured client-side error.

    The title is a single clipped line so GitHub de-dupes visually; the body is
    Markdown with the stack and environment fenced for readability.
    """
    summary = _clip(message, _MAX_TITLE - len("[bug] ")) or "Unhandled client error"
    title = f"[bug] {summary}"

    lines = [
        "_Filed automatically by the dashboard error reporter._",
        "",
        "### What happened",
        _clip(message, _MAX_FIELD) or "_(no message)_",
    ]
    if context.strip():
        lines += ["", "### Context", _clip(context, _MAX_FIELD)]
    env: list[str] = []
    if url.strip():
        env.append(f"- **URL:** {_clip(url, 500)}")
    if user_agent.strip():
        env.append(f"- **User agent:** {_clip(user_agent, 500)}")
    if env:
        lines += ["", "### Environment", *env]
    if stack.strip():
        lines += ["", "### Stack trace", "```", _clip(stack, _MAX_FIELD), "```"]
    return title, "\n".join(lines)


def format_feature_request(*, title: str, details: str, requester: str) -> tuple[str, str]:
    """Return ``(title, body)`` for an approved feature request."""
    summary = _clip(title, _MAX_TITLE - len("[feature] ")) or "Feature request"
    issue_title = f"[feature] {summary}"
    body = "\n".join(
        [
            "_Approved via the dashboard feature-request flow._",
            "",
            f"**Requested by:** {_clip(requester, 200) or 'unknown'}",
            "",
            "### Request",
            _clip(details, _MAX_FIELD) or _clip(title, _MAX_FIELD),
        ]
    )
    return issue_title, body


def approval_email(*, title: str, requester: str, link: str) -> tuple[str, str]:
    """Return ``(subject, body)`` for the approver's magic-link email."""
    subject = f"Approve feature request: {_clip(title, 80)}"
    body = "\n".join(
        [
            f"{_clip(requester, 200) or 'A trustee'} requested a new feature:",
            "",
            f"  {_clip(title, 200)}",
            "",
            "Approve it (this files a tracked issue) by opening:",
            link,
            "",
            "If you don't recognise this request, ignore this email — nothing",
            "happens until the link is opened.",
        ]
    )
    return subject, body
