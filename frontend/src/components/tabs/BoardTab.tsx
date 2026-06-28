"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { StatusChip } from "@/components/StatusChip";
import { RetryableError, SkeletonCards } from "@/components/LoadState";
import { useApi } from "@/lib/useApi";
import { useNotify } from "@/components/Notifications";
import { reportAndNotify } from "@/lib/errorReporting";
import type { Ticket, TicketStatus } from "@/lib/types";

const COLUMNS: TicketStatus[] = ["todo", "in_progress", "done"];
const COLUMN_LABEL: Record<TicketStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
};
const NEXT: Partial<Record<TicketStatus, TicketStatus>> = {
  todo: "in_progress",
  in_progress: "done",
};

const TYPE_OPTIONS = [
  "general",
  "maintenance",
  "financial",
  "complaint",
  "governance",
  "compliance",
];

/** Title-cases a lowercase API enum value for display (the value stays lower). */
function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function BoardTab() {
  const api = useApi();
  const notify = useNotify();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [title, setTitle] = useState("");
  const [type, setType] = useState("general");
  const [priority, setPriority] = useState("normal");
  const [error, setError] = useState<string | null>(null);
  // Loading -> (empty | data) for the board (separate from add/advance errors).
  const [listError, setListError] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready">("loading");
  const [busy, setBusy] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const data = await api.listTickets(signal);
        setTickets(data);
        setListError(null);
      } catch (err) {
        if (!signal?.aborted) {
          setListError(
            err instanceof ApiError ? err.detail : "Failed to load tasks.",
          );
          void reportAndNotify({
            error: err,
            context: "board.load",
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

  /** "Try again" on a failed load: re-show the skeleton, then re-fetch. */
  function retryLoad() {
    setListError(null);
    setLoadState("loading");
    void refresh();
  }

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createTicket({ title, type, priority });
      setTitle("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to add task.");
      void reportAndNotify({ error: err, context: "board.add", api, notify });
    } finally {
      setBusy(false);
    }
  }

  async function advance(ticket: Ticket) {
    const next = NEXT[ticket.status];
    if (!next) return;
    try {
      await api.setTicketStatus(ticket.id, { status: next });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to move task.");
      void reportAndNotify({
        error: err,
        context: "board.advance",
        api,
        notify,
      });
    }
  }

  return (
    <div className="two-col">
      <section className="panel" aria-labelledby="task-add-heading">
        <h2 id="task-add-heading">Add a task</h2>
        <p className="hint">Raise a reminder for the Chairperson.</p>
        <form onSubmit={onAdd}>
          <label>
            Title
            <input
              ref={titleRef}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Describe the task to be done…"
              required
            />
          </label>
          <label>
            Type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {titleCase(t)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Priority
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            >
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
          </label>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Adding…" : "Add task"}
          </button>
        </form>
        {error && <div className="banner error">{error}</div>}
      </section>
      <section className="panel" aria-labelledby="board-heading">
        <h2 id="board-heading">Trustee Task Board</h2>
        {loadState === "loading" ? (
          <SkeletonCards />
        ) : listError ? (
          <RetryableError message={listError} onRetry={retryLoad} />
        ) : tickets.length === 0 ? (
          <div className="empty-state">
            <p className="hint">No tasks yet.</p>
            <button
              className="btn"
              type="button"
              onClick={() => titleRef.current?.focus()}
            >
              Add your first task
            </button>
          </div>
        ) : (
          <div className="board">
            {COLUMNS.map((col) => (
              <div key={col} className="col" data-status={col}>
                <h3>{COLUMN_LABEL[col]}</h3>
                {tickets
                  .filter((t) => t.status === col)
                  .map((t) => (
                    <div key={t.id} className="card">
                      <h4>{t.title}</h4>
                      <div className="meta">
                        {t.type} · {t.priority}
                        {t.unit ? ` · ${t.unit}` : ""}
                      </div>
                      <div className="card-actions">
                        <StatusChip status={t.status} />
                        {NEXT[t.status] && (
                          <button
                            className="btn ghost"
                            onClick={() => advance(t)}
                            type="button"
                          >
                            Move &rarr;
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
