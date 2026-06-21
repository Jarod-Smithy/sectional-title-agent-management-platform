"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { Document } from "@/lib/types";

const CATEGORIES = [
  "rules",
  "finance",
  "maintenance",
  "governance",
  "compliance",
  "general",
];

export function DocumentsTab() {
  const api = useApi();
  const [docs, setDocs] = useState<Document[]>([]);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("general");
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setDocs(await api.listDocuments(signal));
      } catch (err) {
        if (!signal?.aborted) {
          setError(
            err instanceof ApiError ? err.detail : "Failed to load documents.",
          );
        }
      }
    },
    [api],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    void refresh(ctrl.signal);
    return () => ctrl.abort();
  }, [refresh]);

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.addDocument({ title, category, content, overwrite: true });
      setTitle("");
      setContent("");
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Failed to save document.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="two-col">
      <section className="panel" aria-labelledby="doc-add-heading">
        <h2 id="doc-add-heading">Add a document</h2>
        <p className="hint">
          Paste plain text to add it to the document brain.
        </p>
        <form onSubmit={onAdd}>
          <label>
            Title
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </label>
          <label>
            Category
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label>
            Content
            <textarea
              rows={6}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              required
            />
          </label>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save to document brain"}
          </button>
        </form>
        {error && <div className="banner error">{error}</div>}
      </section>
      <section className="panel" aria-labelledby="doc-list-heading">
        <h2 id="doc-list-heading">Document brain</h2>
        {docs.length === 0 ? (
          <p className="hint">No documents yet.</p>
        ) : (
          docs.map((d) => (
            <div key={d.id} className="list-row">
              <strong>{d.title}</strong>
              <div className="hint">
                {d.category} · effective {d.effective_date}
              </div>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
