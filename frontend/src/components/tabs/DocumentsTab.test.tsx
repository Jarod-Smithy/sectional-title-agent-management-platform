import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { DocumentsTab } from "./DocumentsTab";
import { config } from "@/lib/config";
import { AuthProvider } from "@/lib/auth";
import { NotificationProvider } from "@/components/Notifications";
import { resetReportedSignatures } from "@/lib/errorReporting";
import { server } from "@/test/msw/server";

const base = config.apiBase;

/** Renders the real tab inside the real providers — only the network is stubbed. */
function renderTab() {
  return render(
    <NotificationProvider>
      <AuthProvider>
        <DocumentsTab />
      </AuthProvider>
    </NotificationProvider>,
  );
}

describe("DocumentsTab — global error capture", () => {
  beforeEach(() => resetReportedSignatures());

  it("files a bug and shows the AI-notified toast with a tracking link when an upload fails", async () => {
    const user = userEvent.setup();
    server.use(
      // The upload pipeline fails at its first network step…
      http.post(`${base}/api/documents/upload-url`, () =>
        HttpResponse.json({ detail: "Upload failed." }, { status: 500 }),
      ),
      // …and the SDLC endpoint opens a tracked GitHub issue.
      http.post(`${base}/api/report-bug`, () =>
        HttpResponse.json({
          number: 42,
          url: "https://github.com/acme/repo/issues/42",
          created: true,
        }),
      ),
    );

    renderTab();

    const file = new File(["hello"], "rules.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText(/^file$/i), file);
    await user.click(
      screen.getByRole("button", { name: /upload to document brain/i }),
    );

    // Global toast: reassuring copy + a clickable link to track the issue.
    // The report is filed by a fire-and-forget `void reportAndNotify(...)`, so
    // the toast appears asynchronously after the round-trip — wait for it
    // explicitly rather than relying on the 1s default (CI runs every suite in
    // parallel, where the default can be exceeded).
    expect(
      await screen.findByText(
        /our AI engineers have automatically been notified/i,
        undefined,
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole(
        "link",
        { name: /track issue #42/i },
        { timeout: 5000 },
      ),
    ).toHaveAttribute("href", "https://github.com/acme/repo/issues/42");
  });
});
