"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useNotify } from "@/components/Notifications";
import { reportAndNotify } from "@/lib/errorReporting";

export function RequestTab() {
  const api = useApi();
  const notify = useNotify();
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (title.trim().length < 3) return;
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const ack = await api.requestFeature({ title, details });
      setNote(`Sent to ${ack.approver} for approval.`);
      setTitle("");
      setDetails("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Could not submit the feature request.",
      );
      void reportAndNotify({
        error: err,
        context: "request.submit",
        api,
        notify,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="two-col">
      <section className="panel" aria-labelledby="request-heading">
        <h2 id="request-heading">Request a feature</h2>
        <p className="hint">
          Describe an improvement. It is emailed to an approver — once they
          approve, a tracked issue is filed for the build pipeline.
        </p>
        <form onSubmit={onSubmit}>
          <label>
            Title
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              minLength={3}
              required
            />
          </label>
          <label>
            Details
            <textarea
              rows={6}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
          </label>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Submitting…" : "Submit for approval"}
          </button>
        </form>
        {note && <div className="banner info">{note}</div>}
        {error && <div className="banner error">{error}</div>}
      </section>
    </div>
  );
}
