import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { ApiClient, ApiError } from "./api";
import { config } from "./config";
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
