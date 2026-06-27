"""Unit tests for the SDLC domain (bug-report formatting). Pure, no I/O."""

from __future__ import annotations

from app.domain.sdlc import (
    approval_email,
    format_bug_report,
    format_feature_request,
)


def test_format_includes_all_sections_when_present() -> None:
    title, body = format_bug_report(
        message="TypeError: x is undefined",
        stack="at foo (app.js:1)\nat bar (app.js:2)",
        url="https://app.example/dashboard",
        user_agent="Mozilla/5.0",
        context="Clicked Approve on draft 7",
    )
    assert title == "[bug] TypeError: x is undefined"
    assert "### What happened" in body
    assert "### Context" in body
    assert "Clicked Approve on draft 7" in body
    assert "### Environment" in body
    assert "https://app.example/dashboard" in body
    assert "Mozilla/5.0" in body
    assert "### Stack trace" in body
    assert "```" in body


def test_format_omits_optional_sections_when_blank() -> None:
    title, body = format_bug_report(message="Boom")
    assert title == "[bug] Boom"
    assert "### What happened" in body
    assert "### Context" not in body
    assert "### Environment" not in body
    assert "### Stack trace" not in body


def test_format_falls_back_on_empty_message() -> None:
    title, body = format_bug_report(message="   ")
    assert title == "[bug] Unhandled client error"
    assert "_(no message)_" in body


def test_long_message_is_clipped_in_title_and_body() -> None:
    long = "E" * 5000
    title, body = format_bug_report(message=long)
    assert len(title) <= len("[bug] ") + 110
    assert title.endswith("…")
    # The body field is clipped to its own (larger) limit and also ellipsised.
    assert "…" in body


def test_feature_request_uses_details_for_body() -> None:
    title, body = format_feature_request(
        title="Dark mode toggle",
        details="Add a theme switch in the header.",
        requester="trustee.chair",
    )
    assert title == "[feature] Dark mode toggle"
    assert "trustee.chair" in body
    assert "Add a theme switch" in body


def test_feature_request_falls_back_to_title_when_no_details() -> None:
    title, body = format_feature_request(title="Export CSV", details="", requester="")
    assert title == "[feature] Export CSV"
    assert "unknown" in body
    assert "Export CSV" in body


def test_approval_email_embeds_the_link() -> None:
    subject, body = approval_email(
        title="Dark mode", requester="trustee", link="https://api/approve?token=abc"
    )
    assert "Dark mode" in subject
    assert "https://api/approve?token=abc" in body
    assert "trustee" in body
