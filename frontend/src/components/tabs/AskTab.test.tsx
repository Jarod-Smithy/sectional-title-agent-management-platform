import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AskTab } from "./AskTab";
import { AuthProvider } from "@/lib/auth";

function renderWithAuth(ui: React.ReactNode) {
  return render(<AuthProvider>{ui}</AuthProvider>);
}

describe("AskTab", () => {
  it("submits a question and renders the grounded answer + sources", async () => {
    const user = userEvent.setup();
    renderWithAuth(<AskTab />);

    await user.type(screen.getByRole("textbox"), "What are the quiet hours?");
    await user.click(screen.getByRole("button", { name: /ask/i }));

    expect(
      await screen.findByText(/Quiet hours are 22:00/),
    ).toBeInTheDocument();
    expect(screen.getByText("Conduct Rules 2024")).toBeInTheDocument();
  });
});
