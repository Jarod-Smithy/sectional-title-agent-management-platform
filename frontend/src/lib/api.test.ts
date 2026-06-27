import { http, HttpResponse } from "msw";
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
