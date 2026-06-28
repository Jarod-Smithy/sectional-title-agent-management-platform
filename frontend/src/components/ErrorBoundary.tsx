"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import type { BugReportIn, IssueCreatedOut } from "@/lib/types";
import type { Notify } from "@/components/Notifications";
import { FALLBACK_COPY, NOTIFIED_COPY } from "@/lib/errorReporting";

type FileState = "idle" | "filing" | "done" | "failed";

interface Props {
  /** Files the captured error; injected so the boundary stays unit-testable. */
  report: (payload: BugReportIn) => Promise<IssueCreatedOut>;
  /**
   * Optional global notifier. When supplied, the boundary surfaces the same
   * "AI engineers notified" toast (with a tracking link when one is available)
   * in addition to its inline fallback UI. Injected so it stays testable.
   */
  notify?: Notify;
  children: ReactNode;
}

interface State {
  error: Error | null;
  filed: FileState;
  issueUrl: string | null;
}

/**
 * Catches render-time errors anywhere below it, shows a recoverable fallback,
 * and AUTOMATICALLY files the error as a bug report (the AI-native SDLC entry
 * point). Error boundaries must be class components — hooks cannot catch render
 * errors — so the API call is injected via the `report` prop.
 */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null, filed: "idle", issueUrl: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    this.setState({ filed: "filing" });
    const payload: BugReportIn = {
      message: error.message || "Unhandled client error",
      stack: `${error.stack ?? ""}\n\nComponent stack:${
        info.componentStack ?? ""
      }`,
      url: typeof window !== "undefined" ? window.location.href : "",
      user_agent: typeof navigator !== "undefined" ? navigator.userAgent : "",
    };
    this.props
      .report(payload)
      .then((out) => {
        this.setState({
          filed: "done",
          issueUrl: out.created ? out.url : null,
        });
        if (out.created && out.url) {
          this.props.notify?.({
            severity: "error",
            message: NOTIFIED_COPY,
            action: { label: `Track issue #${out.number}`, href: out.url },
          });
        } else {
          this.props.notify?.({ severity: "error", message: FALLBACK_COPY });
        }
      })
      .catch(() => {
        this.setState({ filed: "failed" });
        this.props.notify?.({ severity: "error", message: FALLBACK_COPY });
      });
  }

  private readonly reset = (): void =>
    this.setState({ error: null, filed: "idle", issueUrl: null });

  private status(): ReactNode {
    switch (this.state.filed) {
      case "filing":
        return <span>Filing a report…</span>;
      case "done":
        return this.state.issueUrl ? (
          <span>
            Reported —{" "}
            <a href={this.state.issueUrl} target="_blank" rel="noreferrer">
              view the issue
            </a>
            .
          </span>
        ) : (
          <span>The problem was logged.</span>
        );
      case "failed":
        return <span>We couldn’t file an automatic report.</span>;
      default:
        return null;
    }
  }

  override render(): ReactNode {
    if (!this.state.error) return this.props.children;
    return (
      <div className="panel" role="alert">
        <h2>Something went wrong</h2>
        <p>The dashboard hit an unexpected error. {this.status()}</p>
        <button className="btn" type="button" onClick={this.reset}>
          Try again
        </button>
      </div>
    );
  }
}
