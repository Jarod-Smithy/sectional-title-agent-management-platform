"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { StatusChip } from "@/components/StatusChip";
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

export function BoardTab() {
  const api = useApi();
  const notify = useNotify();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [title, setTitle] = useState("");
  const [type, setType] = useState("general");
  const [priority, setPriority] = useState("normal");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setTickets(await api.listTickets(signal));
      } catch (err) {
        if (!signal?.aborted) {
          setError(
            err instanceof ApiError ? err.detail : "Failed to load tasks.",
          );
          void reportAndNotify({
            error: err,
            context: "board.load",
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
    void refresh(ctrl.signal);
    return () => ctrl.abort();
  }, [refresh]);

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
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Obtain 3 quotes for gate motor"
              required
            />
          </label>
          <label>
            Type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {[
                "general",
                "maintenance",
                "financial",
                "complaint",
                "governance",
                "compliance",
              ].map((t) => (
                <option key={t} value={t}>
                  {t}
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
              <option value="normal">normal</option>
              <option value="high">high</option>
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
      </section>
    </div>
  );
}
