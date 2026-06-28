"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { RetryableError, SkeletonList } from "@/components/LoadState";
import { useApi } from "@/lib/useApi";
import { useNotify } from "@/components/Notifications";
import { reportAndNotify } from "@/lib/errorReporting";
import type { Resolution } from "@/lib/types";

export function ResolutionsTab({
  onNavigate,
}: {
  /** Routes the empty-state CTA to a more useful tab (injected by AppShell). */
  onNavigate?: (tab: "documents") => void;
}) {
  const api = useApi();
  const notify = useNotify();
  const [resolutions, setResolutions] = useState<Resolution[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready">("loading");

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const data = await api.listResolutions(signal);
        setResolutions(data);
        setError(null);
      } catch (err) {
        if (!signal?.aborted) {
          setError(
            err instanceof ApiError
              ? err.detail
              : "Failed to load resolutions.",
          );
          void reportAndNotify({
            error: err,
            context: "resolutions.load",
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
    // load() only calls setState after an awaited fetch (no synchronous setState
    // in the effect body), so this on-mount load is intentional.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  /** "Try again" on a failed load: re-show the skeleton, then re-fetch. */
  function retryLoad() {
    setError(null);
    setLoadState("loading");
    void load();
  }

  return (
    <section className="panel" aria-labelledby="res-heading">
      <h2 id="res-heading">Resolution register</h2>
      <p className="hint">
        Signed resolutions are the scheme&rsquo;s source of truth for what the
        trustees may act on.
      </p>
      {loadState === "loading" ? (
        <SkeletonList />
      ) : error ? (
        <RetryableError message={error} onRetry={retryLoad} />
      ) : resolutions.length === 0 ? (
        <div className="empty-state">
          <p className="hint">No resolutions on record.</p>
          {onNavigate && (
            <button
              className="btn"
              type="button"
              onClick={() => onNavigate("documents")}
            >
              Add your documents
            </button>
          )}
        </div>
      ) : (
        resolutions.map((r) => (
          <div key={r.id} className="list-row">
            <strong>{r.title}</strong>{" "}
            <span
              className="chip"
              style={{
                background: r.signed
                  ? "var(--status-done)"
                  : "var(--status-yellow)",
              }}
            >
              {r.signed ? "signed" : "unsigned"}
            </span>
            <div className="hint">
              {r.effective_date}
              {r.unit ? ` · ${r.unit}` : ""}
            </div>
            {r.summary && <p style={{ fontSize: 14 }}>{r.summary}</p>}
          </div>
        ))
      )}
    </section>
  );
}
