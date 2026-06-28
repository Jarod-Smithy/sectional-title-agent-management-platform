import { ApiError, type ApiClient } from "./api";
import type { BugReportIn } from "./types";
import type { Notify } from "@/components/Notifications";

/** User-facing copy shown when an error was filed and a tracked issue exists. */
export const NOTIFIED_COPY =
  "Something went wrong — but our AI engineers have automatically been notified and are already working on a fix.";

/** Fallback copy when we couldn't confirm a tracked issue was opened. */
export const FALLBACK_COPY =
  "Something went wrong. We've logged the issue and our team is on it.";

/** Signatures already filed this session, to throttle duplicate bug reports. */
const reportedSignatures = new Set<string>();

/** Test helper: clears the in-memory dedup set between cases. */
export function resetReportedSignatures(): void {
  reportedSignatures.clear();
}

/**
 * A *connectivity* condition rather than a bug: the request never reached a
 * working server. For this persona (trustees on slow/intermittent mobile) a
 * brief WiFi drop is the COMMON case, so these must NOT be filed as bugs or
 * shown the alarming "engineers notified" toast. {@link api.ts} normalises both
 * fetch transport failures and request timeouts to an `ApiError` with
 * `status === 0`, so a single check covers offline, dropped TCP, CORS and
 * timeout.
 */
export function isConnectivityError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 0;
}

/**
 * Decide whether a caught error is worth filing as a bug. Only genuine *server
 * faults* (HTTP 5xx) and unexpected runtime errors (a thrown non-`ApiError`,
 * e.g. a real coding fault) qualify. Expected client outcomes — auth (401/403),
 * not-found (404), validation/conflict (4xx) — are surfaced inline by the
 * caller, and *connectivity* conditions (`status === 0`: offline/timeout) are a
 * calm, recoverable everyday event — neither must spam the issue tracker or
 * wake the SDLC agent.
 */
export function isReportableError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status >= 500;
  }
  return true;
}

export interface ReportAndNotifyArgs {
  /** The caught error (any throwable). */
  error: unknown;
  /** Where it happened, e.g. "documents.upload" — used for dedup + triage. */
  context: string;
  /** Anything exposing {@link ApiClient.reportBug}; injected for testability. */
  api: Pick<ApiClient, "reportBug">;
  /** The notifier from {@link useNotify}; injected for testability. */
  notify: Notify;
}

/**
 * Files a caught runtime error as a GitHub issue (via the backend) and shows
 * the user a reassuring notification with a link to track the issue.
 *
 * Pure/injectable — pass `api` and `notify` so it is unit-testable without
 * globals. It never throws: the reporting path must not surface a second error
 * to the user. A client-side dedup set throttles repeat filings of the same
 * `${context}|${message}` signature while STILL notifying the user each time.
 */
export async function reportAndNotify({
  error,
  context,
  api,
  notify,
}: ReportAndNotifyArgs): Promise<void> {
  // Expected client errors (4xx) are handled inline by the caller — never file
  // them as bugs. Only unexpected transport/runtime errors and 5xx reach here.
  if (!isReportableError(error)) {
    return;
  }

  const message =
    error instanceof Error ? error.message : String(error ?? "Unknown error");
  const stack = error instanceof Error ? error.stack : undefined;
  const signature = `${context}|${message}`;

  // Already filed this exact failure this session: reassure the user again,
  // but don't open a duplicate issue.
  if (reportedSignatures.has(signature)) {
    notify({ severity: "error", message: NOTIFIED_COPY });
    return;
  }
  reportedSignatures.add(signature);

  const payload: BugReportIn = {
    message: message || "Unhandled client error",
    ...(stack ? { stack } : {}),
    ...(typeof window !== "undefined" ? { url: window.location.href } : {}),
    ...(typeof navigator !== "undefined"
      ? { user_agent: navigator.userAgent }
      : {}),
    context,
  };

  try {
    const out = await api.reportBug(payload);
    if (out.created && out.url) {
      notify({
        severity: "error",
        message: NOTIFIED_COPY,
        action: { label: `Track issue #${out.number}`, href: out.url },
      });
    } else {
      // SDLC offline tracker (created === false): no live issue link.
      notify({ severity: "error", message: FALLBACK_COPY });
    }
  } catch {
    // Reporting itself failed — degrade gracefully, never re-throw.
    notify({ severity: "error", message: FALLBACK_COPY });
  }
}
