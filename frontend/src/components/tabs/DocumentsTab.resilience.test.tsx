import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient } from "@/lib/api";
import { NotificationProvider } from "@/components/Notifications";
import { resetReportedSignatures } from "@/lib/errorReporting";
import type { Document } from "@/lib/types";

// Only the API boundary is stubbed (via the `useApi` seam); the component,
// NotificationProvider, reportAndNotify and the loading/error state machine are
// all REAL. This exercises the P0 resilience behaviours deterministically.
const api = vi.hoisted(() => ({
  listDocuments: vi.fn(),
  reportBug: vi.fn(),
}));

vi.mock("@/lib/useApi", () => ({
  useApi: () => api as unknown as ApiClient,
}));

import { DocumentsTab } from "./DocumentsTab";

function renderTab() {
  return render(
    <NotificationProvider>
      <DocumentsTab />
    </NotificationProvider>,
  );
}

const sampleDoc: Document = {
  id: 1,
  title: "Conduct Rules 2024",
  category: "rules",
  effective_date: "2024-01-01",
  created_at: "2024-01-01T00:00:00Z",
};

describe("DocumentsTab — loading / connectivity / retry", () => {
  beforeEach(() => {
    resetReportedSignatures();
    vi.clearAllMocks();
    api.reportBug.mockResolvedValue({
      number: 1,
      url: "https://github.com/acme/repo/issues/1",
      created: true,
    });
  });

  it("shows skeleton placeholders, NOT the empty copy, before the first load resolves", async () => {
    let resolveLoad: (docs: Document[]) => void = () => {};
    api.listDocuments.mockReturnValue(
      new Promise<Document[]>((resolve) => {
        resolveLoad = resolve;
      }),
    );

    renderTab();

    // While the fetch is in flight: skeleton is shown and the "No documents
    // yet." empty copy must NOT appear (that's what made the app look broken).
    expect(
      screen.getByRole("status", { name: /loading/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/no documents yet/i)).not.toBeInTheDocument();

    // Only once the fetch resolves (to an empty list) does the empty copy show.
    resolveLoad([]);
    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /upload your first document/i }),
    ).toBeInTheDocument();
  });

  it("shows a calm inline offline message and does NOT file a bug on a connectivity failure", async () => {
    api.listDocuments.mockRejectedValue(
      new ApiError(0, "You appear to be offline — check your connection."),
    );

    renderTab();

    expect(await screen.findByText(/offline/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
    // A brief WiFi drop is the common case for this persona — never a bug.
    expect(api.reportBug).not.toHaveBeenCalled();
  });

  it("re-fetches when the user clicks Try again after a failed load", async () => {
    const user = userEvent.setup();
    api.listDocuments
      .mockRejectedValueOnce(new ApiError(0, "You appear to be offline."))
      .mockResolvedValueOnce([sampleDoc]);

    renderTab();

    const retry = await screen.findByRole("button", { name: /try again/i });
    await user.click(retry);

    expect(await screen.findByText("Conduct Rules 2024")).toBeInTheDocument();
    await waitFor(() => expect(api.listDocuments).toHaveBeenCalledTimes(2));
  });
});
