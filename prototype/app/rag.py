"""Local retrieval for the document brain (Vision §4.4-4.5).

Stands in for a Bedrock Knowledge Base; the call sites (drafting, ask) stay
identical when we swap in embeddings later. Built on best practices distilled
from Anthropic's Contextual Retrieval and Pinecone's chunking guidance, adapted
to run on the Python standard library only (no embeddings, no external deps):

* **Structure-aware chunking** — splits on headings, then paragraphs, then
  sentences/words, packing to a ~900-char target so chunks stay semantically
  coherent rather than cut mid-thought.
* **Contextual prefix** — each chunk is indexed with a short "Title › Heading"
  context line plus a small overlap tail from the previous chunk. This is the
  stdlib approximation of Anthropic's Contextual Retrieval (which prepends
  chunk-specific context before embedding) and meaningfully lifts recall.
* **BM25 ranking** — Okapi BM25 over the chunk + interaction corpus, replacing
  the old naive token-overlap score. BM25 reliably surfaces exact terms and
  identifiers (unit numbers, "geyser", "levy") that a bag-of-words overlap
  under-weights.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from . import db

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

# Chunking targets. ~900 chars ≈ a few hundred tokens, the sweet spot the
# research recommends for policy/correspondence text, with ~15% overlap to
# preserve context across boundaries.
_CHUNK_CHARS = 900
_OVERLAP_CHARS = 150
# Recursive split separators, coarsest → finest (LangChain-style).
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# BM25 hyper-parameters (Okapi defaults).
_BM25_K1 = 1.5
_BM25_B = 0.75


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass
class Chunk:
    ordinal: int
    heading: str
    text: str  # clean chunk content (what we show as a snippet)
    context: str  # "Title › Heading" + overlap tail, used only for indexing
    char_start: int
    char_end: int


_HEADING_MD = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$")
_HEADING_LABEL = re.compile(r"^([A-Z][\w &/'\-]{1,40}):\s")


def _heading_of(para: str) -> str:
    """Best-effort heading for a paragraph (markdown heading or 'Label:' lead)."""
    first = para.lstrip().split("\n", 1)[0]
    m = _HEADING_MD.match(first)
    if m:
        return m.group(1).strip()
    m = _HEADING_LABEL.match(para.lstrip())
    if m:
        return m.group(1).strip()
    return ""


def _recursive_split(text: str, target: int, seps: list[str]) -> list[str]:
    """Split text into pieces ≤ target, preferring the coarsest separator."""
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

    # Paragraph spans (text + offset into the original content).
    paras: list[tuple[str, int]] = []
    pos = 0
    for raw in re.split(r"\n\s*\n", content):
        idx = content.find(raw, pos)
        if idx < 0:
            idx = pos
        if raw.strip():
            paras.append((raw.strip(), idx))
        pos = idx + len(raw)

    # Pack paragraphs into ~target-sized pieces, hard-splitting any giant para.
    pieces: list[tuple[str, int]] = []  # (text, char_start)
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
        if i > 0:  # overlap tail of the previous piece aids cross-boundary recall
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


def index_document(cur, doc_id: int, title: str, content: str) -> int:
    """Chunk a document and persist its chunks. Returns the chunk count."""
    chunks = chunk_document(title, content)
    for ch in chunks:
        cur.execute(
            "INSERT INTO doc_chunks (doc_id, ordinal, heading, context, text, char_start, char_end) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, ch.ordinal, ch.heading, ch.context, ch.text, ch.char_start, ch.char_end),
        )
    return len(chunks)


def chunk_text(text: str) -> list[str]:
    """Back-compat helper: chunk text without a known title."""
    return [c.text for c in chunk_document("", text)]


@dataclass
class Hit:
    title: str
    snippet: str
    kind: str
    score: float


def _bm25(corpus: list[dict], qtokens: list[str], *, limit: int) -> list[Hit]:
    n = len(corpus)
    if n == 0:
        return []
    avgdl = sum(len(d["tokens"]) for d in corpus) / n or 1.0
    df: dict[str, int] = {}
    for d in corpus:
        for t in set(d["tokens"]):
            df[t] = df.get(t, 0) + 1
    qset = set(qtokens)
    hits: list[Hit] = []
    for d in corpus:
        dl = len(d["tokens"]) or 1
        tf: dict[str, int] = {}
        for t in d["tokens"]:
            if t in qset:
                tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t, f in tf.items():
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / avgdl)
            score += idf * (f * (_BM25_K1 + 1)) / denom
        if score > 0:
            hits.append(Hit(d["title"], d["snippet"], d["kind"], score))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def search(query: str, *, limit: int = 5) -> list[Hit]:
    qtokens = tokenize(query)
    if not qtokens:
        return []
    corpus: list[dict] = []
    with db.cursor() as cur:
        cur.execute(
            "SELECT c.context AS context, c.text AS text, d.title AS title "
            "FROM doc_chunks c JOIN documents d ON d.id = c.doc_id"
        )
        for row in cur.fetchall():
            blob = f"{row['context']} {row['text']}"
            corpus.append(
                {
                    "title": row["title"],
                    "snippet": row["text"],
                    "kind": "document",
                    "tokens": tokenize(blob),
                }
            )
        cur.execute(
            "SELECT subject, body, party, direction FROM interactions " "ORDER BY id DESC LIMIT 200"
        )
        for row in cur.fetchall():
            blob = f"{row['subject']} {row['body']}"
            corpus.append(
                {
                    "title": f"{row['direction']} · {row['party']} · {row['subject']}",
                    "snippet": blob,
                    "kind": "interaction",
                    "tokens": tokenize(blob),
                }
            )
    return _bm25(corpus, qtokens, limit=limit)


def context_snippets(query: str, *, limit: int = 5) -> list[str]:
    return [h.snippet for h in search(query, limit=limit)]
