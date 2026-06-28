import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient } from "@/lib/api";
import { NotificationProvider } from "@/components/Notifications";
import { resetReportedSignatures } from "@/lib/errorReporting";

// The API is injected at its `useApi` seam so this integration test is fully
// deterministic — no network or auth-provider timing (the source of CI-only
// flakiness). The component, NotificationProvider, reportAndNotify and the toast
// are all REAL; only the API boundary is stubbed: the upload fails and the SDLC
// endpoint opens a tracked issue.
const api = vi.hoisted(() => ({
  listDocuments: vi.fn(),
  requestDocumentUploadUrl: vi.fn(),
  reportBug: vi.fn(),
}));

vi.mock("@/lib/useApi", () => ({
  useApi: () => api as unknown as ApiClient,
}));

import { DocumentsTab } from "./DocumentsTab";

describe("DocumentsTab — global error capture", () => {
  beforeEach(() => {
    resetReportedSignatures();
    vi.clearAllMocks();
    api.listDocuments.mockResolvedValue([]);
    api.requestDocumentUploadUrl.mockRejectedValue(
      new ApiError(500, "Upload failed."),
    );
    api.reportBug.mockResolvedValue({
      number: 42,
      url: "https://github.com/acme/repo/issues/42",
      created: true,
    });
  });

  it("files a bug and shows the AI-notified toast with a tracking link when an upload fails", async () => {
    const user = userEvent.setup();
    render(
      <NotificationProvider>
        <DocumentsTab />
      </NotificationProvider>,
    );

    const file = new File(["hello"], "rules.txt", { type: "text/plain" });
    const input = screen.getByLabelText(/^file$/i);
    await user.upload(input, file);
    // Submit the form directly: jsdom's constraint validation for a `required`
    // file input doesn't recognise files set via userEvent, so a submit-button
    // click is suppressed. fireEvent.submit faithfully drives the real onSubmit
    // handler (a valid file passes validation in a real browser).
    fireEvent.submit(input.closest("form")!);

    // The upload was attempted and its failure was filed as a single bug…
    await waitFor(() =>
      expect(api.requestDocumentUploadUrl).toHaveBeenCalledTimes(1),
    );
    await waitFor(() => expect(api.reportBug).toHaveBeenCalledTimes(1));

    // …and the user sees the reassuring toast with a link to track the issue.
    expect(
      await screen.findByText(
        /our AI engineers have automatically been notified/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /track issue #42/i }),
    ).toHaveAttribute("href", "https://github.com/acme/repo/issues/42");
  });
});
