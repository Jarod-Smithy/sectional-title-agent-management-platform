"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { SeverityChip } from "@/components/StatusChip";
import { config } from "@/lib/config";
import { useApi } from "@/lib/useApi";
import { useNotify } from "@/components/Notifications";
import { reportAndNotify } from "@/lib/errorReporting";
import type { Draft } from "@/lib/types";

export function InboxTab() {
  const api = useApi();
  const notify = useNotify();
  const [sender, setSender] = useState("owner.surname@gmail.com");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setDrafts(await api.listDrafts("pending", signal));
      } catch (err) {
        if (!signal?.aborted) {
          setError(
            err instanceof ApiError ? err.detail : "Failed to load drafts.",
          );
          void reportAndNotify({
            error: err,
            context: "inbox.load",
            api,
            notify,
          });
        }
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

  async function onProcess(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim() || !body.trim()) return;
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const out = await api.inbox({ sender, subject, body });
      setNote(
        out.kind === "task"
          ? "Routed to a board task."
          : "Draft reply created below.",
      );
      setSubject("");
      setBody("");
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Failed to process email.",
      );
      void reportAndNotify({
        error: err,
        context: "inbox.process",
        api,
        notify,
      });
    } finally {
      setBusy(false);
    }
  }

  async function approve(id: number) {
    try {
      await api.approveDraft(id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not file draft.");
      void reportAndNotify({
        error: err,
        context: "inbox.approve",
        api,
        notify,
      });
    }
  }

  async function discard(id: number) {
    try {
      await api.discardDraft(id);
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Could not discard draft.",
      );
      void reportAndNotify({
        error: err,
        context: "inbox.discard",
        api,
        notify,
      });
    }
  }

  return (
    <div className="two-col">
      {config.features.simulatedIntake && (
        <section className="panel" aria-labelledby="email-heading">
          <h2 id="email-heading">Simulate an inbound email</h2>
          <form onSubmit={onProcess}>
            <label>
              From
              <input
                value={sender}
                onChange={(e) => setSender(e.target.value)}
                required
              />
            </label>
            <label>
              Subject
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
              />
            </label>
            <label>
              Body
              <textarea
                rows={5}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                required
              />
            </label>
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Processing…" : "Process → draft reply"}
            </button>
          </form>
          {note && <div className="banner info">{note}</div>}
        </section>
      )}
      <section className="panel" aria-labelledby="drafts-heading">
        <h2 id="drafts-heading">Drafts awaiting approval</h2>
        {error && <div className="banner error">{error}</div>}
        {drafts.length === 0 ? (
          <p className="hint">No pending drafts.</p>
        ) : (
          drafts.map((d) => (
            <div key={d.id} className="list-row">
              <strong>{d.inbound_subject}</strong>{" "}
              <span className="hint">
                · {d.party} · {d.case_ref}
              </span>
              <p style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>{d.body}</p>
              {d.findings.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    gap: 6,
                    flexWrap: "wrap",
                    marginBottom: 8,
                  }}
                >
                  {d.findings.map((f, i) => (
                    <SeverityChip key={i} severity={f.severity} />
                  ))}
                </div>
              )}
              <div className="card-actions">
                <button
                  className="btn"
                  type="button"
                  onClick={() => approve(d.id)}
                >
                  Approve &amp; file
                </button>
                <button
                  className="btn ghost"
                  type="button"
                  onClick={() => discard(d.id)}
                >
                  Discard
                </button>
              </div>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
