import type { Severity, TicketStatus } from "@/lib/types";

const STATUS_FILL: Record<TicketStatus, string> = {
  todo: "var(--status-info)",
  in_progress: "var(--status-working)",
  done: "var(--status-done)",
};

const STATUS_LABEL: Record<TicketStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
};

const SEVERITY_FILL: Record<Severity, string> = {
  block: "var(--status-stuck)",
  warn: "var(--status-working)",
  info: "var(--status-info)",
};

/** Plain-English labels for guardrail severities (the raw codes mean nothing
 * to a trustee). */
const SEVERITY_LABEL: Record<Severity, string> = {
  block: "Must fix",
  warn: "Check",
  info: "Note",
};

/** A monday-style coloured status chip for ticket board states. */
export function StatusChip({ status }: { status: TicketStatus }) {
  return (
    <span
      className="chip"
      style={{
        background: STATUS_FILL[status],
        color: status === "done" ? "#0a3b25" : "#171a22",
      }}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

/** A coloured chip for guardrail finding severities (white text on red). */
export function SeverityChip({ severity }: { severity: Severity }) {
  return (
    <span
      className="chip"
      style={{
        background: SEVERITY_FILL[severity],
        color: severity === "block" ? "#ffffff" : "#171a22",
      }}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
