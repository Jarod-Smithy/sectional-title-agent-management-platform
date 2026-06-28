"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { useNotify } from "@/components/Notifications";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AskTab } from "@/components/tabs/AskTab";
import { BoardTab } from "@/components/tabs/BoardTab";
import { DocumentsTab } from "@/components/tabs/DocumentsTab";
import { InboxTab } from "@/components/tabs/InboxTab";
import { RequestTab } from "@/components/tabs/RequestTab";
import { ResolutionsTab } from "@/components/tabs/ResolutionsTab";

export type TabKey =
  | "inbox"
  | "board"
  | "resolutions"
  | "ask"
  | "documents"
  | "request";

// "Request a Feature" is intentionally absent — it's demoted to a small header
// "Feedback" link below (it's not a daily trustee task and crowded the primary
// nav). "Documents" leads because it's the first useful action for a brand-new
// trustee; the old default ("inbox") opened an empty read-only drafts panel.
const TABS: { key: TabKey; label: string }[] = [
  { key: "documents", label: "Documents" },
  { key: "ask", label: "Ask a question" },
  { key: "inbox", label: "Inbox" },
  { key: "board", label: "Task Board" },
  { key: "resolutions", label: "Resolutions" },
];

/** Tracks navigator.onLine so we can show a calm, dismissible offline banner. */
function useOnline(): boolean {
  const [online, setOnline] = useState(
    typeof navigator === "undefined" ? true : navigator.onLine,
  );
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

export function AppShell() {
  const { email, signOut } = useAuth();
  const api = useApi();
  const notify = useNotify();
  const [active, setActive] = useState<TabKey>("documents");
  const online = useOnline();

  return (
    <>
      <header className="app-header">
        <div>
          <h1>Trustee Platform</h1>
          <span className="scheme">Acacia Heights Body Corporate</span>
        </div>
        <div className="header-right">
          {email && <span>{email}</span>}
          <button
            className="btn-link"
            type="button"
            onClick={() => setActive("request")}
          >
            Feedback
          </button>
          <button className="btn ghost" type="button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      {!online && (
        <div className="banner offline" role="status">
          You appear to be offline — some things may not load until your
          connection is back.
        </div>
      )}

      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={active === t.key ? "active" : ""}
            aria-current={active === t.key ? "page" : undefined}
            onClick={() => setActive(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="content">
        <ErrorBoundary
          report={(payload) => api.reportBug(payload)}
          notify={notify}
        >
          {active === "inbox" && (
            <InboxTab onNavigate={(tab) => setActive(tab)} />
          )}
          {active === "board" && <BoardTab />}
          {active === "resolutions" && (
            <ResolutionsTab onNavigate={(tab) => setActive(tab)} />
          )}
          {active === "ask" && <AskTab />}
          {active === "documents" && <DocumentsTab />}
          {active === "request" && <RequestTab />}
        </ErrorBoundary>
      </main>
    </>
  );
}
