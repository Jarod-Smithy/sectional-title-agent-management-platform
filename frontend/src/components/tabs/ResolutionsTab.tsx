"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { Resolution } from "@/lib/types";

export function ResolutionsTab() {
  const api = useApi();
  const [resolutions, setResolutions] = useState<Resolution[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .listResolutions(ctrl.signal)
      .then(setResolutions)
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) {
          setError(
            err instanceof ApiError
              ? err.detail
              : "Failed to load resolutions.",
          );
        }
      });
    return () => ctrl.abort();
  }, [api]);

  return (
    <section className="panel" aria-labelledby="res-heading">
      <h2 id="res-heading">Resolution register</h2>
      <p className="hint">
        Signed resolutions are the scheme&rsquo;s source of truth for what the
        trustees may act on.
      </p>
      {error && <div className="banner error">{error}</div>}
      {resolutions.length === 0 && !error ? (
        <p className="hint">No resolutions on record.</p>
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
