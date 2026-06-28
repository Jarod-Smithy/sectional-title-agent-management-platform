"""Unit tests for the S3 document store + native text extraction.

No network: ``S3DocumentStore`` takes an INJECTED fake boto3 ``s3`` client, and
the optional ``pypdf`` dependency is faked via ``importlib`` so PDF extraction
is exercised deterministically whether or not ``pypdf`` is installed.
"""

from __future__ import annotations

import importlib
import io
from typing import Any

import pytest
from app.adapters.s3_documents import S3DocumentStore, extract_text
from app.bootstrap import build_document_store
from app.settings import Settings


class _FakeS3:
    """Stands in for the boto3 ``s3`` client."""

    def __init__(self, *, contents: list[str] | None = None, body: bytes = b"") -> None:
        self._contents = contents or []
        self._body = body
        self.presign_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str:
        self.presign_calls.append({"args": args, "kwargs": kwargs})
        return "https://bucket.s3.amazonaws.com/signed-put"

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        return {"Contents": [{"Key": key} for key in self._contents]}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append(kwargs)
        return {"Body": io.BytesIO(self._body)}


# ── S3DocumentStore ───────────────────────────────────────────────────────────
def test_presign_put_passes_bucket_key_and_expiry() -> None:
    client = _FakeS3()
    store = S3DocumentStore(client=client, bucket="docs-bucket")
    url = store.presign_put(key="uploads/a/f.txt", content_type="text/plain", expires_in=900)
    assert url == "https://bucket.s3.amazonaws.com/signed-put"
    call = client.presign_calls[0]
    assert call["args"][0] == "put_object"
    assert call["kwargs"]["Params"] == {
        "Bucket": "docs-bucket",
        "Key": "uploads/a/f.txt",
        "ContentType": "text/plain",
    }
    assert call["kwargs"]["ExpiresIn"] == 900


def test_list_keys_returns_keys_then_empty() -> None:
    store = S3DocumentStore(client=_FakeS3(contents=["uploads/a/f.txt"]), bucket="b")
    assert store.list_keys(prefix="uploads/a/") == ["uploads/a/f.txt"]
    empty = S3DocumentStore(client=_FakeS3(contents=[]), bucket="b")
    assert empty.list_keys(prefix="uploads/none/") == []


def test_get_object_reads_body_bytes() -> None:
    store = S3DocumentStore(client=_FakeS3(body=b"raw bytes"), bucket="b")
    assert store.get_object(key="uploads/a/f.bin") == b"raw bytes"


# ── extract_text ──────────────────────────────────────────────────────────────
def test_extract_text_decodes_text_extensions() -> None:
    assert extract_text("notes.txt", b"hello world") == "hello world"
    assert extract_text("data.md", b"# Title") == "# Title"


def test_extract_text_decodes_unknown_binary_as_utf8() -> None:
    assert extract_text("blob.dat", b"plain text") == "plain text"


def test_extract_text_empty_unknown_yields_notice() -> None:
    out = extract_text("blob.dat", b"")
    assert out.startswith("[Empty document")


def test_extract_text_undecodable_binary_yields_notice() -> None:
    out = extract_text("blob.dat", b"\xff\xfe\xff")
    assert "No extractable text" in out


def test_extract_text_pdf_without_pypdf_yields_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pypdf":
            raise ImportError("pypdf not installed")
        return real_import(name, *args, **kwargs)  # pragma: no cover

    monkeypatch.setattr(importlib, "import_module", fake_import)
    out = extract_text("scan.pdf", b"%PDF-1.4 ...")
    assert "No extractable text" in out


def test_extract_text_pdf_with_pypdf_extracts_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _Reader:
        def __init__(self, _stream: Any) -> None:
            self.pages = [_Page("Page one."), _Page("Page two.")]

    fake_module: Any = type("_FakePypdf", (), {"PdfReader": _Reader})
    real_import = importlib.import_module

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pypdf":
            return fake_module
        return real_import(name, *args, **kwargs)  # pragma: no cover

    monkeypatch.setattr(importlib, "import_module", fake_import)
    # Magic-byte detection (no .pdf extension) still routes through the PDF path.
    out = extract_text("scan.bin", b"%PDF-1.4 body")
    assert out == "Page one.\n\nPage two."


def test_extract_text_pdf_malformed_yields_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Reader:
        def __init__(self, _stream: Any) -> None:
            raise ValueError("corrupt pdf")

    fake_module: Any = type("_FakePypdf", (), {"PdfReader": _Reader})
    real_import = importlib.import_module

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pypdf":
            return fake_module
        return real_import(name, *args, **kwargs)  # pragma: no cover

    monkeypatch.setattr(importlib, "import_module", fake_import)
    out = extract_text("scan.pdf", b"%PDF-broken")
    assert "No extractable text" in out


# ── Composition root + settings seams ─────────────────────────────────────────
def test_build_document_store_is_none_without_bucket() -> None:
    assert build_document_store(Settings(documents_bucket="")) is None


def test_build_document_store_returns_adapter_with_bucket() -> None:
    store = build_document_store(
        Settings(documents_bucket="docs-bucket", documents_region="af-south-1")
    )
    assert isinstance(store, S3DocumentStore)


def test_build_document_store_presigns_regional_virtual_hosted_url() -> None:
    """Presigned PUT URLs must use the regional virtual-hosted endpoint.

    boto3 defaults to the global ``s3.amazonaws.com`` endpoint which is blocked
    by the CloudFront CSP (connect-src only allows *.s3.<region>.amazonaws.com).
    The fix is ``addressing_style='virtual'`` on the S3 client config, which
    produces ``https://<bucket>.s3.<region>.amazonaws.com/...`` URLs.
    """
    store = build_document_store(
        Settings(documents_bucket="my-docs-bucket", documents_region="af-south-1")
    )
    assert isinstance(store, S3DocumentStore)
    url = store.presign_put(key="test.pdf", content_type="application/pdf", expires_in=300)
    # Must be virtual-hosted regional form, NOT the global s3.amazonaws.com endpoint.
    assert "my-docs-bucket.s3.af-south-1.amazonaws.com" in url, (
        f"Expected regional virtual-hosted URL, got: {url}"
    )


def test_documents_resolved_region_prefers_explicit_then_falls_back() -> None:
    assert Settings(documents_region="eu-west-1").documents_resolved_region == "eu-west-1"
    fallback = Settings(documents_region="", aws_region="af-south-1")
    assert fallback.documents_resolved_region == "af-south-1"


def test_upload_url_expiry_has_a_safe_default() -> None:
    assert Settings().upload_url_expiry_seconds == 900
