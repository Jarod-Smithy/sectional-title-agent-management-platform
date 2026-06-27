// Wire contract types — mirror services/api/app/schemas.py 1:1.
// Keep field names identical so the typed client matches the FastAPI responses.

export type Severity = "block" | "warn" | "info";
export type SourceKind = "document" | "interaction";
export type DraftStatus = "pending" | "filed" | "auto_filed" | "discarded";
export type TicketStatus = "todo" | "in_progress" | "done";
export type TicketSource = "email" | "chair_email" | "manual" | "resolution";

export interface Document {
  id: number;
  title: string;
  category: string;
  effective_date: string;
  created_at: string;
}

export interface DocumentIn {
  title: string;
  content: string;
  category?: string;
  effective_date?: string;
  overwrite?: boolean;
}

export interface DocumentUploadUrlIn {
  filename: string;
  contentType: string;
}

export interface DocumentUploadUrlOut {
  documentId: string;
  key: string;
  uploadUrl: string;
}

export interface AnalyzeIn {
  content: string;
  filename?: string;
}

export interface AnalyzeOut {
  title: string;
  category: string;
  effective_date: string;
  char_count: number;
  chunk_count: number;
  preview: string;
  llm: string;
}

export interface AskIn {
  question: string;
}

export interface Source {
  title: string;
  snippet: string;
  kind: SourceKind;
}

export interface AskOut {
  answer: string;
  sources: Source[];
}

export interface EmailIn {
  sender: string;
  subject: string;
  body: string;
  from_unit?: string;
}

export interface GuardrailFinding {
  rule: string;
  severity: Severity;
  message: string;
}

export interface Draft {
  id: number;
  interaction_id: number;
  intent: string;
  party: string;
  from_unit: string;
  unit: string;
  case_ref: string;
  priority: string;
  inbound_subject: string;
  inbound_snippet: string;
  body: string;
  status: DraftStatus;
  auto_send_eligible: boolean;
  findings: GuardrailFinding[];
  sources: Source[];
  created_at: string;
}

export interface InboxOut {
  kind: "draft" | "task";
  draft: Draft | null;
  ticket: Ticket | null;
}

export interface DraftEdit {
  body: string;
}

export interface Ticket {
  id: number;
  title: string;
  type: string;
  status: TicketStatus;
  priority: string;
  unit: string;
  case_ref: string;
  assignee: string;
  source_interaction_id: number | null;
  created_at: string;
  due_date: string;
  description: string;
  source: TicketSource;
  source_resolution_id: number | null;
  topic_key: string;
}

export interface TicketIn {
  title: string;
  type?: string;
  priority?: string;
  unit?: string;
  due_date?: string;
  description?: string;
  source?: TicketSource;
  source_resolution_id?: number | null;
}

export interface TicketStatusIn {
  status: TicketStatus;
}

export interface Resolution {
  id: number;
  title: string;
  effective_date: string;
  signed: boolean;
  summary: string;
  keywords: string;
  unit: string;
}

export interface Health {
  status: "ok";
  engine: string;
  repo_backend: string;
  assist_available: boolean;
  version: string;
}

export interface AssistConfig {
  assist_enabled: boolean;
  kill_switch: boolean;
  available: boolean;
}

export interface BugReportIn {
  message: string;
  stack?: string;
  url?: string;
  user_agent?: string;
  context?: string;
}

export interface IssueCreatedOut {
  number: number;
  url: string;
  created: boolean;
}

export interface FeatureRequestIn {
  title: string;
  details?: string;
}

export interface FeatureRequestAck {
  status: "pending_approval";
  approver: string;
}
