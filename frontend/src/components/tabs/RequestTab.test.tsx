import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { RequestTab } from "./RequestTab";
import { config } from "@/lib/config";
import { AuthProvider } from "@/lib/auth";
import { server } from "@/test/msw/server";

const base = config.apiBase;

function renderWithAuth(ui: React.ReactNode) {
  return render(<AuthProvider>{ui}</AuthProvider>);
}

describe("RequestTab", () => {
  it("submits a feature request and confirms who it was sent to", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${base}/api/feature-request`, () =>
        HttpResponse.json({
          status: "pending_approval",
          approver: "approver@example.com",
        }),
      ),
    );
    renderWithAuth(<RequestTab />);

    await user.type(screen.getByLabelText(/title/i), "Dark mode");
    await user.click(
      screen.getByRole("button", { name: /submit for approval/i }),
    );

    expect(
      await screen.findByText(/Sent to approver@example.com for approval\./),
    ).toBeInTheDocument();
    // On success the title field is cleared for the next request.
    expect(screen.getByLabelText(/title/i)).toHaveValue("");
  });

  it("shows the server detail when approval is not configured", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${base}/api/feature-request`, () =>
        HttpResponse.json(
          { detail: "Feature-request approval is not configured." },
          { status: 503 },
        ),
      ),
    );
    renderWithAuth(<RequestTab />);

    await user.type(screen.getByLabelText(/title/i), "Dark mode");
    await user.click(
      screen.getByRole("button", { name: /submit for approval/i }),
    );

    expect(
      await screen.findByText(/approval is not configured/i),
    ).toBeInTheDocument();
  });

  it("does not submit when the title is shorter than three characters", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(
      http.post(`${base}/api/feature-request`, () => {
        called = true;
        return HttpResponse.json({
          status: "pending_approval",
          approver: "approver@example.com",
        });
      }),
    );
    renderWithAuth(<RequestTab />);

    await user.type(screen.getByLabelText(/title/i), "ab");
    await user.click(
      screen.getByRole("button", { name: /submit for approval/i }),
    );

    expect(called).toBe(false);
    expect(
      screen.queryByText(/sent to .* for approval/i),
    ).not.toBeInTheDocument();
  });
});
