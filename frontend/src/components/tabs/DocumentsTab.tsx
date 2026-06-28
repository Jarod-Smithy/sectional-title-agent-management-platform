"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useNotify } from "@/components/Notifications";
import { RetryableError, SkeletonList } from "@/components/LoadState";
import { reportAndNotify } from "@/lib/errorReporting";
import type { AnalyzeOut, Document } from "@/lib/types";

const CATEGORIES = [
  "rules",
  "finance",
  "maintenance",
  "governance",
  "compliance",
  "general",
];

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const MAX_FILE_MB = MAX_FILE_BYTES / (1024 * 1024);

const ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt"] as const;
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];
const ACCEPT_ATTR = [...ACCEPTED_EXTENSIONS, ...ACCEPTED_MIME_TYPES].join(",");

/** Upload pipeline phases — drives the inline progress message. */
type UploadPhase = "idle" | "requesting" | "uploading" | "confirming";

const PHASE_LABEL: Record<Exclude<UploadPhase, "idle">, string> = {
  requesting: "Requesting a secure upload link…",
  uploading: "Uploading to storage…",
  confirming: "Confirming and indexing…",
};

/** Rejects unsupported types/sizes before we touch the network. */
function validateFile(file: File): string | null {
  const lower = file.name.toLowerCase();
  const extOk = ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
  // Some browsers report an empty MIME type; fall back to the extension check.
  const typeOk = file.type === "" || ACCEPTED_MIME_TYPES.includes(file.type);
  if (!extOk || !typeOk) {
    return "Unsupported file type. Upload a PDF, Word (.doc/.docx) or .txt file.";
  }
  if (file.size > MAX_FILE_BYTES) {
    return `File is too large — the maximum is ${MAX_FILE_MB} MB.`;
  }
  return null;
}

export function DocumentsTab() {
  const api = useApi();
  const notify = useNotify();
  const [docs, setDocs] = useState<Document[]>([]);
  const [error, setError] = useState<string | null>(null);
  // The document list runs an explicit loading -> (empty | data) machine so the
  // "No documents yet." copy never shows before the first fetch has resolved.
  const [listError, setListError] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready">("loading");

  // ── Upload (primary path) ──────────────────────────────────────────────────
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [success, setSuccess] = useState<string | null>(null);
  const uploading = phase !== "idle";

  // ── Paste text (advanced fallback) ──────────────────────────────────────────
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("general");
  const [content, setContent] = useState("");
  const [pasteBusy, setPasteBusy] = useState(false);
  const [analysis, setAnalysis] = useState<AnalyzeOut | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const data = await api.listDocuments(signal);
        setDocs(data);
        setListError(null);
      } catch (err) {
        if (!signal?.aborted) {
          setListError(
            err instanceof ApiError ? err.detail : "Failed to load documents.",
          );
          void reportAndNotify({
            error: err,
            context: "documents.load",
            api,
            notify,
          });
        }
      } finally {
        if (!signal?.aborted) setLoadState("ready");
      }
    },
    [api, notify],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    // refresh() only calls setState after an awaited fetch (no synchronous
    // setState in the effect body), so this on-mount load is intentional.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh(ctrl.signal);
    return () => ctrl.abort();
  }, [refresh]);

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    setError(null);
    setSuccess(null);
    const picked = e.target.files?.[0] ?? null;
    if (picked) {
      const validationError = validateFile(picked);
      if (validationError) {
        setError(validationError);
        setFile(null);
        return;
      }
    }
    setFile(picked);
  }

  function resetFileInput() {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  /** Empty-state CTA: jump straight to the file picker (the primary action). */
  function focusUpload() {
    fileInputRef.current?.focus();
    fileInputRef.current?.click();
  }

  /** "Try again" on a failed list load: re-show the skeleton, then re-fetch. */
  function retryLoad() {
    setListError(null);
    setLoadState("loading");
    void refresh();
  }

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setSuccess(null);
    const contentType = file.type || "application/octet-stream";
    try {
      setPhase("requesting");
      const { documentId, uploadUrl } = await api.requestDocumentUploadUrl({
        filename: file.name,
        contentType,
      });
      setPhase("uploading");
      await api.uploadFileToS3(uploadUrl, file);
      setPhase("confirming");
      const stored = await api.confirmDocument(documentId);
      setSuccess(`Uploaded “${stored.title}”.`);
      resetFileInput();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Upload failed.");
      void reportAndNotify({
        error: err,
        context: "documents.upload",
        api,
        notify,
      });
    } finally {
      setPhase("idle");
    }
  }

  async function onAnalyze() {
    if (!content.trim()) return;
    setAnalyzing(true);
    setError(null);
    try {
      setAnalysis(
        await api.analyzeDocument({
          content,
          filename: title.trim() || undefined,
        }),
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Failed to analyze content.",
      );
      void reportAndNotify({
        error: err,
        context: "documents.analyze",
        api,
        notify,
      });
    } finally {
      setAnalyzing(false);
    }
  }

  async function onAddText(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setPasteBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const stored = await api.addDocument({
        title,
        category,
        content,
        overwrite: true,
      });
      setSuccess(`Saved “${stored.title}”.`);
      setTitle("");
      setContent("");
      setAnalysis(null);
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Failed to save document.",
      );
      void reportAndNotify({
        error: err,
        context: "documents.save",
        api,
        notify,
      });
    } finally {
      setPasteBusy(false);
    }
  }

  return (
    <div className="two-col">
      <section className="panel" aria-labelledby="doc-add-heading">
        <h2 id="doc-add-heading">Add a document</h2>
        <p className="hint">
          Upload a PDF, Word (.doc/.docx) or .txt file (max {MAX_FILE_MB} MB).
          The file is stored securely and added to your documents.
        </p>
        <form onSubmit={onUpload}>
          <label>
            File
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_ATTR}
              onChange={onPickFile}
              disabled={uploading}
              aria-describedby="doc-upload-status"
              required
            />
          </label>
          {file && (
            <p className="hint">
              {file.name} · {(file.size / 1024).toFixed(0)} KB
            </p>
          )}
          <button className="btn" type="submit" disabled={uploading || !file}>
            {uploading ? "Uploading…" : "Upload document"}
          </button>
        </form>
        <div id="doc-upload-status" aria-live="polite">
          {uploading && (
            <div className="banner info" role="status">
              {PHASE_LABEL[phase]}
            </div>
          )}
          {success && <div className="banner info">{success}</div>}
          {error && <div className="banner error">{error}</div>}
        </div>

        <details className="advanced">
          <summary>Advanced: paste plain text instead</summary>
          <form onSubmit={onAddText}>
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
                onChange={(e) => {
                  setContent(e.target.value);
                  setAnalysis(null);
                }}
                required
              />
            </label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                className="btn"
                type="button"
                onClick={onAnalyze}
                disabled={analyzing || pasteBusy || !content.trim()}
              >
                {analyzing ? "Analyzing…" : "Analyze"}
              </button>
              <button className="btn" type="submit" disabled={pasteBusy}>
                {pasteBusy ? "Saving…" : "Save to your documents"}
              </button>
            </div>
          </form>
          {analysis && (
            <div className="banner info" role="status">
              Detected <strong>{analysis.category}</strong> ·{" "}
              {analysis.char_count} chars · effective {analysis.effective_date}
              <div className="hint">{analysis.preview}</div>
            </div>
          )}
        </details>
      </section>
      <section className="panel" aria-labelledby="doc-list-heading">
        <h2 id="doc-list-heading">Your documents</h2>
        {loadState === "loading" ? (
          <SkeletonList />
        ) : listError ? (
          <RetryableError message={listError} onRetry={retryLoad} />
        ) : docs.length === 0 ? (
          <div className="empty-state">
            <p className="hint">No documents yet.</p>
            <button className="btn" type="button" onClick={focusUpload}>
              Upload your first document
            </button>
          </div>
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
