import { http, HttpResponse } from "msw";
import { config } from "@/lib/config";
import type { AskOut, Document, Health, Ticket } from "@/lib/types";

const base = config.apiBase;

export const sampleDocuments: Document[] = [
  {
    id: 1,
    title: "Conduct Rules 2024",
    category: "rules",
    effective_date: "2024-01-01",
    created_at: "2024-01-01T00:00:00Z",
  },
];

export const sampleTickets: Ticket[] = [
  {
    id: 1,
    title: "Obtain 3 quotes for gate motor",
    type: "maintenance",
    status: "todo",
    priority: "high",
    unit: "",
    case_ref: "AH-0001",
    assignee: "",
    source_interaction_id: null,
    created_at: "2024-02-01T00:00:00Z",
    due_date: "",
    description: "",
    source: "manual",
    source_resolution_id: null,
    topic_key: "",
  },
];

const health: Health = {
  status: "ok",
  engine: "stub",
  repo_backend: "sqlite",
  assist_available: true,
  version: "0.1.0",
};

const askAnswer: AskOut = {
  answer: "Quiet hours are 22:00–06:00 per the conduct rules.",
  sources: [
    { title: "Conduct Rules 2024", snippet: "Quiet hours…", kind: "document" },
  ],
};

/** Default happy-path handlers; individual tests override with server.use(). */
export const handlers = [
  http.get(`${base}/api/health`, () => HttpResponse.json(health)),
  http.get(`${base}/api/documents`, () => HttpResponse.json(sampleDocuments)),
  http.post(`${base}/api/documents`, async ({ request }) => {
    const body = (await request.json()) as { title: string; category?: string };
    return HttpResponse.json({
      id: 2,
      title: body.title,
      category: body.category ?? "general",
      effective_date: "2024-06-01",
      created_at: "2024-06-01T00:00:00Z",
    } satisfies Document);
  }),
  http.get(`${base}/api/tickets`, () => HttpResponse.json(sampleTickets)),
  http.get(`${base}/api/resolutions`, () => HttpResponse.json([])),
  http.get(`${base}/api/drafts`, () => HttpResponse.json([])),
  http.post(`${base}/api/ask`, () => HttpResponse.json(askAnswer)),
];
