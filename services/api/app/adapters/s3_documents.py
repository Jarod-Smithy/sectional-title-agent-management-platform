"""S3 document store + native text extraction.

Implements :class:`app.ports.documents.DocumentStore` against Amazon S3 and
provides :func:`extract_text`, a dependency-light text extractor.

Design notes:
* The boto3 ``s3`` client is INJECTED (a small Protocol), so this module imports
  no AWS SDK and stays trivially unit-testable. The composition root
  (:mod:`app.bootstrap`) builds the real client only when a bucket is set.
* Uploads go browser → S3 directly via a short-lived presigned PUT; the API
  never streams file bytes. On confirm we read the object back and extract text.
* Extraction is "native" (in-process, no Textract): text-like payloads decode
  as UTF-8; PDFs use ``pypdf`` IF it is importable, otherwise (and for any other
  binary) we store a short notice so the document still registers.
"""

from __future__ import annotations

import importlib
import io
from typing import Any, Protocol

# Content/extension hints we treat as directly decodable UTF-8 text.
_TEXT_EXTENSIONS = (".txt", ".md", ".markdown", ".csv", ".json", ".log", ".text")


class _S3Client(Protocol):
    """The boto3 ``s3`` methods this adapter needs."""

    def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str: ...

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...


class S3DocumentStore:
    """Presigned-PUT uploads + read-back over a single private S3 bucket."""

    def __init__(self, *, client: _S3Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def presign_put(self, *, key: str, content_type: str, expires_in: int) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )

    def list_keys(self, *, prefix: str) -> list[str]:
        resp = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
        contents = resp.get("Contents", []) or []
        return [str(item["Key"]) for item in contents if item.get("Key")]

    def get_object(self, *, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        body = resp["Body"].read()
        return bytes(body)


def _looks_like_pdf(filename: str, data: bytes) -> bool:
    return filename.lower().endswith(".pdf") or data[:5] == b"%PDF-"


def _extract_pdf(data: bytes) -> str | None:
    """Best-effort native PDF text extraction; ``None`` if unavailable/empty.

    ``pypdf`` is optional (not a hard dependency); when it is absent or the PDF
    yields no text we fall back to a notice so the document still registers. It
    is loaded via ``importlib`` so a missing package is a clean runtime branch
    rather than a static import error.
    """
    pypdf: Any
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError:
        return None
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception:  # any malformed-PDF error → fall back to notice
        return None
    text = "\n\n".join(p.strip() for p in pages if p.strip()).strip()
    return text or None


def extract_text(filename: str, data: bytes) -> str:
    """Extract document text natively; never raises.

    Text-like payloads decode as UTF-8 (lossy). PDFs use ``pypdf`` when present.
    Anything non-extractable yields a short, human-readable notice so the upload
    still produces a registered document.
    """
    lowered = filename.lower()
    if lowered.endswith(_TEXT_EXTENSIONS):
        return data.decode("utf-8", errors="replace").strip()
    if _looks_like_pdf(filename, data):
        extracted = _extract_pdf(data)
        if extracted is not None:
            return extracted
        return f"[No extractable text from '{filename}'. The file was uploaded and stored.]"
    # Unknown/binary: attempt a UTF-8 decode, else a notice.
    try:
        decoded = data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return f"[No extractable text from '{filename}'. The file was uploaded and stored.]"
    return decoded or f"[Empty document '{filename}'.]"
