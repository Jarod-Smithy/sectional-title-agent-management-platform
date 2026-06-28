import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { ApiClient, ApiError } from "./api";
import { config } from "./config";
import { sampleUploadUrl } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";

const base = config.apiBase;

describe("ApiClient", () => {
  it("fetches health without requiring a token", async () => {
    const api = new ApiClient(() => null);
    const health = await api.health();
    expect(health.status).toBe("ok");
    expect(health.engine).toBe("stub");
  });

  it("lists documents", async () => {
    const api = new ApiClient(() => "token");
    const docs = await api.listDocuments();
    expect(docs).toHaveLength(1);
    expect(docs[0]?.title).toBe("Conduct Rules 2024");
  });

  it("attaches the bearer token on authenticated calls", async () => {
    let seen: string | null = null;
    server.use(
      http.get(`${base}/api/tickets`, ({ request }) => {
        seen = request.headers.get("authorization");
        return HttpResponse.json([]);
      }),
    );
    const api = new ApiClient(() => "abc123");
    await api.listTickets();
    expect(seen).toBe("Bearer abc123");
  });

  it("omits the Authorization header when signed out", async () => {
    let seen: string | null = "unset";
    server.use(
      http.get(`${base}/api/tickets`, ({ request }) => {
        seen = request.headers.get("authorization");
        return HttpResponse.json([]);
      }),
    );
    const api = new ApiClient(() => null);
    await api.listTickets();
    expect(seen).toBeNull();
  });

  it("creates a document via POST", async () => {
    const api = new ApiClient(() => "token");
    const doc = await api.addDocument({ title: "New rules", content: "text" });
    expect(doc.id).toBe(2);
    expect(doc.title).toBe("New rules");
  });

  it("requests a presigned upload URL", async () => {
    const api = new ApiClient(() => "token");
    const out = await api.requestDocumentUploadUrl({
      filename: "rules.pdf",
      contentType: "application/pdf",
    });
    expect(out.documentId).toBe("doc-42");
    expect(out.key).toBe("incoming/rules.pdf");
    expect(out.uploadUrl).toBe(sampleUploadUrl);
  });

  it("PUTs the file to S3 with the content type and no bearer token", async () => {
    let auth: string | null = "unset";
    let contentType: string | null = null;
    server.use(
      http.put(sampleUploadUrl, ({ request }) => {
        auth = request.headers.get("authorization");
        contentType = request.headers.get("content-type");
        return new HttpResponse(null, { status: 200 });
      }),
    );
    const api = new ApiClient(() => "abc123");
    const file = new File(["hello"], "rules.txt", { type: "text/plain" });
    await api.uploadFileToS3(sampleUploadUrl, file);
    expect(auth).toBeNull();
    expect(contentType).toBe("text/plain");
  });

  it("raises ApiError when the S3 PUT fails", async () => {
    server.use(
      http.put(sampleUploadUrl, () => new HttpResponse(null, { status: 403 })),
    );
    const api = new ApiClient(() => "token");
    const file = new File(["hello"], "rules.txt", { type: "text/plain" });
    await expect(
      api.uploadFileToS3(sampleUploadUrl, file),
    ).rejects.toMatchObject({ name: "ApiError", status: 403 });
  });

  it("confirms an uploaded document", async () => {
    const api = new ApiClient(() => "token");
    const doc = await api.confirmDocument("doc-42");
    expect(doc.title).toBe("Stored doc-42");
  });

  it("raises ApiError with the server detail on a 401", async () => {
    server.use(
      http.get(`${base}/api/tickets`, () =>
        HttpResponse.json({ detail: "Not authenticated" }, { status: 401 }),
      ),
    );
    const api = new ApiClient(() => null);
    await expect(api.listTickets()).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      detail: "Not authenticated",
    });
  });

  it("returns a typed answer from /api/ask", async () => {
    const api = new ApiClient(() => "token");
    const out = await api.ask({ question: "quiet hours?" });
    expect(out.answer).toContain("Quiet hours");
    expect(out.sources[0]?.kind).toBe("document");
  });

  it("exposes ApiError as an Error subclass", () => {
    const err = new ApiError(500, "boom");
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe("API 500: boom");
  });
});

describe("ApiClient — connectivity + timeouts", () => {
  it("normalises a dropped/offline connection to a connectivity ApiError(0)", async () => {
    server.use(http.get(`${base}/api/documents`, () => HttpResponse.error()));
    const api = new ApiClient(() => "token");
    const err = await api.listDocuments().catch((e: unknown) => e);
    expect(err).toMatchObject({ name: "ApiError", status: 0 });
    expect((err as ApiError).detail).toMatch(/offline/i);
  });

  it("times out a slow read and surfaces a connectivity ApiError(0)", async () => {
    server.use(
      http.get(`${base}/api/documents`, async () => {
        await delay(200);
        return HttpResponse.json([]);
      }),
    );
    // A 20ms deadline guarantees the timeout fires before the 200ms handler.
    const api = new ApiClient(() => "token", undefined, { readTimeoutMs: 20 });
    const err = await api.listDocuments().catch((e: unknown) => e);
    expect(err).toMatchObject({ name: "ApiError", status: 0 });
    expect((err as ApiError).detail).toMatch(/longer than expected/i);
  });

  it("does not swallow a genuine HTTP error as a connectivity failure", async () => {
    server.use(
      http.get(`${base}/api/documents`, () =>
        HttpResponse.json({ detail: "Server boom" }, { status: 500 }),
      ),
    );
    const api = new ApiClient(() => "token");
    await expect(api.listDocuments()).rejects.toMatchObject({
      name: "ApiError",
      status: 500,
    });
  });
});

describe("ApiClient — write + SDLC routes", () => {
  it("posts content to /api/documents/analyze and returns the metadata", async () => {
    let sent: { content: string; filename?: string } | null = null;
    server.use(
      http.post(`${base}/api/documents/analyze`, async ({ request }) => {
        sent = (await request.json()) as { content: string; filename?: string };
        return HttpResponse.json({
          title: "House Rules",
          category: "rules",
          effective_date: "2024-06-01",
          char_count: 42,
          chunk_count: 2,
          preview: "House Rules…",
          llm: "StubLLM",
        });
      }),
    );
    const api = new ApiClient(() => "token");
    const out = await api.analyzeDocument({
      content: "Keep common areas tidy.",
      filename: "rules.txt",
    });
    expect(sent).toEqual({
      content: "Keep common areas tidy.",
      filename: "rules.txt",
    });
    expect(out.title).toBe("House Rules");
    expect(out.chunk_count).toBe(2);
  });

  it("routes an inbound email through /api/inbox", async () => {
    server.use(
      http.post(`${base}/api/inbox`, () =>
        HttpResponse.json({
          kind: "draft",
          draft: { id: 5, intent: "maintenance" },
          ticket: null,
        }),
      ),
    );
    const api = new ApiClient(() => "token");
    const out = await api.inbox({
      sender: "jane@example.com",
      subject: "Leak",
      body: "Water everywhere.",
    });
    expect(out.kind).toBe("draft");
    expect(out.draft?.id).toBe(5);
  });

  it("passes the status filter as a query param when listing drafts", async () => {
    let seenUrl: string | null = null;
    server.use(
      http.get(`${base}/api/drafts`, ({ request }) => {
        seenUrl = request.url;
        return HttpResponse.json([]);
      }),
    );
    const api = new ApiClient(() => "token");
    await api.listDrafts("pending");
    expect(seenUrl).not.toBeNull();
    expect(new URL(seenUrl!).searchParams.get("status")).toBe("pending");
  });

  it("edits a draft via PUT with the new body", async () => {
    let sent: { body: string } | null = null;
    server.use(
      http.put(`${base}/api/drafts/7`, async ({ request }) => {
        sent = (await request.json()) as { body: string };
        return HttpResponse.json({ id: 7, body: "Edited.", status: "pending" });
      }),
    );
    const api = new ApiClient(() => "token");
    const draft = await api.editDraft(7, { body: "Edited." });
    expect(sent).toEqual({ body: "Edited." });
    expect(draft.id).toBe(7);
  });

  it("approves a draft with an overriding body when one is supplied", async () => {
    let sent: unknown = "unset";
    server.use(
      http.post(`${base}/api/drafts/7/approve`, async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ id: 7, status: "filed" });
      }),
    );
    const api = new ApiClient(() => "token");
    const draft = await api.approveDraft(7, "Final wording.");
    expect(sent).toEqual({ body: "Final wording." });
    expect(draft.status).toBe("filed");
  });

  it("approves a draft with no request body when none is supplied", async () => {
    let raw = "unset";
    server.use(
      http.post(`${base}/api/drafts/7/approve`, async ({ request }) => {
        raw = await request.text();
        return HttpResponse.json({ id: 7, status: "filed" });
      }),
    );
    const api = new ApiClient(() => "token");
    await api.approveDraft(7);
    expect(raw).toBe("");
  });

  it("surfaces a guardrail block (409) from approveDraft as an ApiError", async () => {
    server.use(
      http.post(`${base}/api/drafts/7/approve`, () =>
        HttpResponse.json({ detail: "Blocked by guardrail." }, { status: 409 }),
      ),
    );
    const api = new ApiClient(() => "token");
    await expect(api.approveDraft(7)).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      detail: "Blocked by guardrail.",
    });
  });

  it("discards a draft via POST", async () => {
    server.use(
      http.post(`${base}/api/drafts/7/discard`, () =>
        HttpResponse.json({ id: 7, status: "discarded" }),
      ),
    );
    const api = new ApiClient(() => "token");
    const draft = await api.discardDraft(7);
    expect(draft.status).toBe("discarded");
  });

  it("creates a ticket via POST", async () => {
    let sent: { title: string } | null = null;
    server.use(
      http.post(`${base}/api/tickets`, async ({ request }) => {
        sent = (await request.json()) as { title: string };
        return HttpResponse.json({ id: 9, title: "Fix gate", status: "todo" });
      }),
    );
    const api = new ApiClient(() => "token");
    const ticket = await api.createTicket({ title: "Fix gate" });
    expect(sent).toEqual({ title: "Fix gate" });
    expect(ticket.id).toBe(9);
  });

  it("updates a ticket status via POST", async () => {
    let sent: { status: string } | null = null;
    server.use(
      http.post(`${base}/api/tickets/9/status`, async ({ request }) => {
        sent = (await request.json()) as { status: string };
        return HttpResponse.json({ id: 9, status: "in_progress" });
      }),
    );
    const api = new ApiClient(() => "token");
    const ticket = await api.setTicketStatus(9, { status: "in_progress" });
    expect(sent).toEqual({ status: "in_progress" });
    expect(ticket.status).toBe("in_progress");
  });

  it("lists resolutions", async () => {
    server.use(
      http.get(`${base}/api/resolutions`, () =>
        HttpResponse.json([{ id: 1, title: "Levy increase 2025" }]),
      ),
    );
    const api = new ApiClient(() => "token");
    const resolutions = await api.listResolutions();
    expect(resolutions).toHaveLength(1);
    expect(resolutions[0]?.title).toBe("Levy increase 2025");
  });

  it("reads the assist config toggle", async () => {
    server.use(
      http.get(`${base}/api/assist/config`, () =>
        HttpResponse.json({
          assist_enabled: true,
          kill_switch: false,
          available: true,
        }),
      ),
    );
    const api = new ApiClient(() => "token");
    const cfg = await api.getAssistConfig();
    expect(cfg.available).toBe(true);
  });

  it("files a captured error through /api/report-bug", async () => {
    let sent: { message: string } | null = null;
    server.use(
      http.post(`${base}/api/report-bug`, async ({ request }) => {
        sent = (await request.json()) as { message: string };
        return HttpResponse.json({
          number: 0,
          url: "log:not-created",
          created: false,
        });
      }),
    );
    const api = new ApiClient(() => "token");
    const out = await api.reportBug({ message: "TypeError: boom" });
    expect(sent).toEqual({ message: "TypeError: boom" });
    expect(out.created).toBe(false);
    expect(out.number).toBe(0);
  });

  it("surfaces a tracker failure (502) from reportBug as an ApiError", async () => {
    server.use(
      http.post(`${base}/api/report-bug`, () =>
        HttpResponse.json(
          { detail: "Could not file the bug report." },
          { status: 502 },
        ),
      ),
    );
    const api = new ApiClient(() => "token");
    await expect(api.reportBug({ message: "kaboom" })).rejects.toMatchObject({
      name: "ApiError",
      status: 502,
    });
  });

  it("submits a feature request for emailed approval", async () => {
    let sent: { title: string; details?: string } | null = null;
    server.use(
      http.post(`${base}/api/feature-request`, async ({ request }) => {
        sent = (await request.json()) as { title: string; details?: string };
        return HttpResponse.json({
          status: "pending_approval",
          approver: "approver@example.com",
        });
      }),
    );
    const api = new ApiClient(() => "token");
    const ack = await api.requestFeature({
      title: "Dark mode",
      details: "A theme switch.",
    });
    expect(sent).toEqual({ title: "Dark mode", details: "A theme switch." });
    expect(ack.status).toBe("pending_approval");
    expect(ack.approver).toBe("approver@example.com");
  });

  it("surfaces an unconfigured approval flow (503) as an ApiError", async () => {
    server.use(
      http.post(`${base}/api/feature-request`, () =>
        HttpResponse.json(
          { detail: "Feature-request approval is not configured." },
          { status: 503 },
        ),
      ),
    );
    const api = new ApiClient(() => "token");
    await expect(
      api.requestFeature({ title: "Dark mode" }),
    ).rejects.toMatchObject({ name: "ApiError", status: 503 });
  });
});
