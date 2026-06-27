"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AskTab } from "@/components/tabs/AskTab";
import { BoardTab } from "@/components/tabs/BoardTab";
import { DocumentsTab } from "@/components/tabs/DocumentsTab";
import { InboxTab } from "@/components/tabs/InboxTab";
import { RequestTab } from "@/components/tabs/RequestTab";
import { ResolutionsTab } from "@/components/tabs/ResolutionsTab";

type TabKey =
  | "inbox"
  | "board"
  | "resolutions"
  | "ask"
  | "documents"
  | "request";

const TABS: { key: TabKey; label: string }[] = [
  { key: "inbox", label: "Inbox" },
  { key: "board", label: "Task Board" },
  { key: "resolutions", label: "Resolutions" },
  { key: "ask", label: "Ask the Records" },
  { key: "documents", label: "Documents" },
  { key: "request", label: "Request a Feature" },
];

export function AppShell() {
  const { email, signOut } = useAuth();
  const api = useApi();
  const [active, setActive] = useState<TabKey>("inbox");

  return (
    <>
      <header className="app-header">
        <div>
          <h1>Trustee Platform</h1>
          <span className="scheme">Acacia Heights Body Corporate</span>
        </div>
        <div className="header-right">
          {email && <span>{email}</span>}
          <button className="btn ghost" type="button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

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
        <ErrorBoundary report={(payload) => api.reportBug(payload)}>
          {active === "inbox" && <InboxTab />}
          {active === "board" && <BoardTab />}
          {active === "resolutions" && <ResolutionsTab />}
          {active === "ask" && <AskTab />}
          {active === "documents" && <DocumentsTab />}
          {active === "request" && <RequestTab />}
        </ErrorBoundary>
      </main>
    </>
  );
}
