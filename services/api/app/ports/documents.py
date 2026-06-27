"""Document-store port — the seam to blob storage for uploaded files.

Presigned PUT lets the browser upload bytes straight to S3 (the API never
streams file payloads). On confirmation the API reads the object back, extracts
text, and indexes it into the existing corpus exactly like the paste-text path.
``S3DocumentStore`` is the production adapter; tests use a structural fake.
"""

from __future__ import annotations

from typing import Protocol


class DocumentStore(Protocol):
    """Blob storage operations the document-upload flow needs."""

    def presign_put(self, *, key: str, content_type: str, expires_in: int) -> str: ...

    def list_keys(self, *, prefix: str) -> list[str]: ...

    def get_object(self, *, key: str) -> bytes: ...
