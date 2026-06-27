"""API tests for the S3 document-upload flow (presign → confirm → index).

Uses a structural fake ``DocumentStore`` injected into ``app.state`` so the
upload endpoints run end-to-end through the FastAPI test client with no AWS.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


class FakeDocumentStore:
    """In-memory stand-in for the S3 document store (the ``DocumentStore`` port)."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self.presigned: list[str] = []
        self.last_expiry: int | None = None

    def presign_put(self, *, key: str, content_type: str, expires_in: int) -> str:
        self.presigned.append(key)
        self.last_expiry = expires_in
        return f"https://fake-bucket.s3.amazonaws.com/{key}"

    def upload(self, key: str, data: bytes) -> None:
        """Test helper: simulate the browser PUT-ing bytes to the presigned URL."""
        self._objects[key] = data

    def list_keys(self, *, prefix: str) -> list[str]:
        return [k for k in self._objects if k.startswith(prefix)]

    def get_object(self, *, key: str) -> bytes:
        return self._objects[key]


@pytest.fixture
def documents_client(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, FakeDocumentStore]]:
    monkeypatch.setenv("STAK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAK_SERVE_STATIC", "false")
    monkeypatch.setenv("STAK_REPO_BACKEND", "sqlite")
    monkeypatch.setenv("STAK_LLM_PROVIDER", "stub")
    monkeypatch.delenv("STAK_SEED_ENABLED", raising=False)

    from app.main import create_app
    from app.settings import get_settings

    get_settings.cache_clear()
    app = create_app()
    store = FakeDocumentStore()
    with TestClient(app) as test_client:
        # Lifespan builds the real store (None without a bucket); swap in the fake.
        app.state.documents = store
        yield test_client, store
    get_settings.cache_clear()


def test_upload_url_then_confirm_registers_and_indexes(
    documents_client: tuple[TestClient, FakeDocumentStore],
) -> None:
    client, store = documents_client

    presign = client.post(
        "/api/documents/upload-url",
        json={"filename": "House Rules.txt", "contentType": "text/plain"},
    )
    assert presign.status_code == 200
    out = presign.json()
    key = out["key"]
    assert key.startswith(f"uploads/{out['documentId']}/")
    assert out["uploadUrl"].endswith(key)
    assert store.presigned == [key]
    assert store.last_expiry == 900

    # Simulate the direct-to-S3 PUT, then confirm.
    store.upload(key, b"Owners must keep common areas tidy.")
    confirm = client.post(f"/api/documents/{out['documentId']}/confirm")
    assert confirm.status_code == 200
    doc = confirm.json()
    assert doc["title"] == "House Rules"

    listed = client.get("/api/documents").json()
    assert any(d["title"] == "House Rules" for d in listed)


def test_confirm_replaces_existing_document_with_same_title(
    documents_client: tuple[TestClient, FakeDocumentStore],
) -> None:
    client, store = documents_client
    # A document with the eventual title already exists (e.g. pasted earlier).
    seeded = client.post(
        "/api/documents",
        json={"title": "House Rules", "content": "Original pasted body."},
    )
    assert seeded.status_code == 200

    out = client.post(
        "/api/documents/upload-url",
        json={"filename": "House Rules.txt", "contentType": "text/plain"},
    ).json()
    store.upload(out["key"], b"Replacement body from upload.")
    confirm = client.post(f"/api/documents/{out['documentId']}/confirm")
    assert confirm.status_code == 200

    titles = [d["title"] for d in client.get("/api/documents").json()]
    assert titles.count("House Rules") == 1  # replaced, not duplicated


def test_upload_url_sanitises_traversal_filename(
    documents_client: tuple[TestClient, FakeDocumentStore],
) -> None:
    client, _ = documents_client
    out = client.post(
        "/api/documents/upload-url",
        json={"filename": "../../../etc/passwd"},
    ).json()
    assert out["key"].endswith("/passwd")


def test_upload_url_blank_filename_falls_back(
    documents_client: tuple[TestClient, FakeDocumentStore],
) -> None:
    client, _ = documents_client
    out = client.post("/api/documents/upload-url", json={"filename": ""}).json()
    assert out["key"].endswith("/upload.bin")


def test_confirm_without_uploaded_object_is_404(
    documents_client: tuple[TestClient, FakeDocumentStore],
) -> None:
    client, _ = documents_client
    resp = client.post("/api/documents/deadbeef/confirm")
    assert resp.status_code == 404


def test_upload_endpoints_503_when_storage_unconfigured(client: TestClient) -> None:
    # The default client configures no bucket → app.state.documents is None.
    presign = client.post("/api/documents/upload-url", json={"filename": "f.txt"})
    assert presign.status_code == 503
    confirm = client.post("/api/documents/abc/confirm")
    assert confirm.status_code == 503


def test_paste_text_path_still_works_without_storage(client: TestClient) -> None:
    created = client.post(
        "/api/documents",
        json={"title": "Pasted Doc", "content": "Pasted body content."},
    )
    assert created.status_code == 200
    assert created.json()["title"] == "Pasted Doc"
