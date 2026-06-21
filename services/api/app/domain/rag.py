"""Local retrieval for the document brain — pure, decoupled from the DB.

Stands in for a Bedrock Knowledge Base; the call sites stay identical when
embeddings are swapped in. Structure-aware chunking + contextual prefix + Okapi
BM25, ported from the prototype. The repository supplies the corpus; this module
holds no I/O.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.ports.repository import Chunk, CorpusItem
from app.schemas import SourceKind

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "be",
    "with",
    "as",
    "at",
    "by",
    "it",
    "this",
    "that",
    "i",
    "we",
    "you",
    "please",
    "regarding",
    "re",
    "dear",
    "hi",
    "hello",
    "kind",
    "regards",
}

_CHUNK_CHARS = 900
_OVERLAP_CHARS = 150
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

_BM25_K1 = 1.5
_BM25_B = 0.75

_HEADING_MD = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$")
_HEADING_LABEL = re.compile(r"^([A-Z][\w &/'\-]{1,40}):\s")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def _heading_of(para: str) -> str:
    first = para.lstrip().split("\n", 1)[0]
    m = _HEADING_MD.match(first)
    if m:
        return m.group(1).strip()
    m = _HEADING_LABEL.match(para.lstrip())
    if m:
        return m.group(1).strip()
    return ""


def _recursive_split(text: str, target: int, seps: list[str]) -> list[str]:
    if len(text) <= target:
        return [text]
    sep = seps[0]
    rest = seps[1:] or [""]
    if sep == "":
        return [text[i : i + target] for i in range(0, len(text), target)]
    parts = text.split(sep)
    out: list[str] = []
    buf = ""
    for part in parts:
        piece = part if not buf else f"{buf}{sep}{part}"
        if len(piece) <= target:
            buf = piece
        else:
            if buf:
                out.append(buf)
                buf = ""
            if len(part) > target:
                out.extend(_recursive_split(part, target, rest))
            else:
                buf = part
    if buf:
        out.append(buf)
    return out


def chunk_document(title: str, content: str) -> list[Chunk]:
    """Structure-aware chunks with a contextual prefix and small overlap."""
    content = content.strip()
    if not content:
        return []

    paras: list[tuple[str, int]] = []
    pos = 0
    for raw in re.split(r"\n\s*\n", content):
        idx = content.find(raw, pos)
        if idx < 0:
            idx = pos
        if raw.strip():
            paras.append((raw.strip(), idx))
        pos = idx + len(raw)

    pieces: list[tuple[str, int]] = []
    buf, buf_start = "", 0
    for para, off in paras:
        if len(para) > _CHUNK_CHARS:
            if buf:
                pieces.append((buf, buf_start))
                buf = ""
            for sub in _recursive_split(para, _CHUNK_CHARS, _SEPARATORS):
                pieces.append((sub.strip(), off))
            continue
        if not buf:
            buf, buf_start = para, off
        elif len(buf) + len(para) + 2 <= _CHUNK_CHARS:
            buf = f"{buf}\n\n{para}"
        else:
            pieces.append((buf, buf_start))
            buf, buf_start = para, off
    if buf:
        pieces.append((buf, buf_start))

    chunks: list[Chunk] = []
    for i, (text, start) in enumerate(pieces):
        heading = _heading_of(text)
        ctx_parts = [p for p in (title.strip(), heading) if p]
        context = " › ".join(ctx_parts)
        if i > 0:
            tail = pieces[i - 1][0][-_OVERLAP_CHARS:]
            cut = tail.find(" ")
            context = f"{context}\n{tail[cut + 1 :] if cut > 0 else tail}".strip()
        chunks.append(
            Chunk(
                ordinal=i,
                heading=heading,
                text=text,
                context=context,
                char_start=start,
                char_end=start + len(text),
            )
        )
    return chunks


@dataclass(frozen=True)
class Hit:
    title: str
    snippet: str
    kind: SourceKind
    score: float


def search(query: str, corpus: list[CorpusItem], *, limit: int = 5) -> list[Hit]:
    """Okapi BM25 ranking of a pre-built corpus (doc chunks + interactions)."""
    qtokens = tokenize(query)
    if not qtokens:
        return []

    docs = [(item, tokenize(item.index_text)) for item in corpus]
    n = len(docs)
    if n == 0:
        return []
    avgdl = sum(len(toks) for _, toks in docs) / n or 1.0

    df: dict[str, int] = {}
    for _, toks in docs:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1

    qset = set(qtokens)
    hits: list[Hit] = []
    for item, toks in docs:
        dl = len(toks) or 1
        tf: dict[str, int] = {}
        for t in toks:
            if t in qset:
                tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t, f in tf.items():
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / avgdl)
            score += idf * (f * (_BM25_K1 + 1)) / denom
        if score > 0:
            hits.append(Hit(item.title, item.snippet, item.kind, score))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]
