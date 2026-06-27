import { config } from "./config";
import type {
  AnalyzeIn,
  AnalyzeOut,
  AskIn,
  AskOut,
  AssistConfig,
  BugReportIn,
  Document,
  DocumentIn,
  DocumentUploadUrlIn,
  DocumentUploadUrlOut,
  Draft,
  DraftEdit,
  EmailIn,
  Health,
  InboxOut,
  IssueCreatedOut,
  Resolution,
  Ticket,
  TicketIn,
  TicketStatusIn,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

/** Resolves the bearer token for the current session, or null when signed out. */
export type TokenProvider = () => string | null;

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * Thin typed client over the FastAPI routes. Every call attaches the Cognito
 * access token (when present) as `Authorization: Bearer`. `/api/health` is the
 * only unauthenticated route.
 */
export class ApiClient {
  constructor(
    private readonly getToken: TokenProvider = () => null,
    private readonly baseUrl: string = config.apiBase,
  ) {}

  private async request<T>(
    path: string,
    opts: RequestOptions = {},
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    const token = this.getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";

    const res = await fetch(`${this.baseUrl}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    });

    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = (await res.json()) as { detail?: string };
        if (typeof data.detail === "string") detail = data.detail;
      } catch {
        // non-JSON error body — keep statusText
      }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  // ── Health ────────────────────────────────────────────────────────────────
  health(signal?: AbortSignal): Promise<Health> {
    return this.request<Health>("/api/health", { signal });
  }

  // ── Documents ─────────────────────────────────────────────────────────────
  listDocuments(signal?: AbortSignal): Promise<Document[]> {
    return this.request<Document[]>("/api/documents", { signal });
  }

  addDocument(payload: DocumentIn): Promise<Document> {
    return this.request<Document>("/api/documents", {
      method: "POST",
      body: payload,
    });
  }

  analyzeDocument(payload: AnalyzeIn): Promise<AnalyzeOut> {
    return this.request<AnalyzeOut>("/api/documents/analyze", {
      method: "POST",
      body: payload,
    });
  }

  /** Step 1 of the upload flow: ask the API for a presigned S3 PUT URL. */
  requestDocumentUploadUrl(
    payload: DocumentUploadUrlIn,
  ): Promise<DocumentUploadUrlOut> {
    return this.request<DocumentUploadUrlOut>("/api/documents/upload-url", {
      method: "POST",
      body: payload,
    });
  }

  /**
   * Step 2 of the upload flow: PUT the raw file bytes straight to S3 using the
   * presigned URL. This bypasses {@link request} on purpose — the presigned URL
   * is absolute and must NOT carry the API base or the `Authorization` bearer
   * (S3 authenticates via the signature embedded in the URL). The `Content-Type`
   * must match what was signed in step 1.
   */
  async uploadFileToS3(uploadUrl: string, file: File): Promise<void> {
    const res = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    if (!res.ok) {
      throw new ApiError(
        res.status,
        res.statusText || "Upload to storage failed",
      );
    }
  }

  /** Step 3 of the upload flow: confirm the upload and persist the document. */
  confirmDocument(documentId: string): Promise<Document> {
    return this.request<Document>(
      `/api/documents/${encodeURIComponent(documentId)}/confirm`,
      { method: "POST" },
    );
  }

  // ── Ask (document brain) ──────────────────────────────────────────────────
  ask(payload: AskIn): Promise<AskOut> {
    return this.request<AskOut>("/api/ask", { method: "POST", body: payload });
  }

  // ── Inbox ─────────────────────────────────────────────────────────────────
  inbox(payload: EmailIn): Promise<InboxOut> {
    return this.request<InboxOut>("/api/inbox", {
      method: "POST",
      body: payload,
    });
  }

  // ── Drafts ────────────────────────────────────────────────────────────────
  listDrafts(status?: string, signal?: AbortSignal): Promise<Draft[]> {
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<Draft[]>(`/api/drafts${q}`, { signal });
  }

  editDraft(id: number, payload: DraftEdit): Promise<Draft> {
    return this.request<Draft>(`/api/drafts/${id}`, {
      method: "PUT",
      body: payload,
    });
  }

  approveDraft(id: number, body?: string): Promise<Draft> {
    return this.request<Draft>(`/api/drafts/${id}/approve`, {
      method: "POST",
      body: body !== undefined ? { body } : undefined,
    });
  }

  discardDraft(id: number): Promise<Draft> {
    return this.request<Draft>(`/api/drafts/${id}/discard`, { method: "POST" });
  }

  // ── Tickets ───────────────────────────────────────────────────────────────
  listTickets(signal?: AbortSignal): Promise<Ticket[]> {
    return this.request<Ticket[]>("/api/tickets", { signal });
  }

  createTicket(payload: TicketIn): Promise<Ticket> {
    return this.request<Ticket>("/api/tickets", {
      method: "POST",
      body: payload,
    });
  }

  setTicketStatus(id: number, payload: TicketStatusIn): Promise<Ticket> {
    return this.request<Ticket>(`/api/tickets/${id}/status`, {
      method: "POST",
      body: payload,
    });
  }

  // ── Resolutions ───────────────────────────────────────────────────────────
  listResolutions(signal?: AbortSignal): Promise<Resolution[]> {
    return this.request<Resolution[]>("/api/resolutions", { signal });
  }

  // ── Assist config ─────────────────────────────────────────────────────────
  getAssistConfig(signal?: AbortSignal): Promise<AssistConfig> {
    return this.request<AssistConfig>("/api/assist/config", { signal });
  }

  // ── SDLC: file a captured error as a bug issue ────────────────────────────
  reportBug(payload: BugReportIn): Promise<IssueCreatedOut> {
    return this.request<IssueCreatedOut>("/api/report-bug", {
      method: "POST",
      body: payload,
    });
  }
}
