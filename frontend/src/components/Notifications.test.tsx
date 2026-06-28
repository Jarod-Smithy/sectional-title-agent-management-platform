import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { NotificationProvider, useNotify } from "./Notifications";

function Dispatcher() {
  const notify = useNotify();
  return (
    <button
      type="button"
      onClick={() =>
        notify({
          severity: "error",
          message: "Something broke.",
          action: { label: "Track issue #7", href: "https://gh/issues/7" },
        })
      }
    >
      go
    </button>
  );
}

describe("NotificationProvider", () => {
  it("renders a dispatched notification with its action link", async () => {
    const user = userEvent.setup();
    render(
      <NotificationProvider>
        <Dispatcher />
      </NotificationProvider>,
    );

    await user.click(screen.getByRole("button", { name: "go" }));

    expect(await screen.findByText("Something broke.")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Track issue #7" });
    expect(link).toHaveAttribute("href", "https://gh/issues/7");
    expect(link).toHaveAttribute("target", "_blank");
    // Error notifications announce assertively.
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("dismisses a notification when its close button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <NotificationProvider>
        <Dispatcher />
      </NotificationProvider>,
    );

    await user.click(screen.getByRole("button", { name: "go" }));
    expect(await screen.findByText("Something broke.")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /dismiss notification/i }),
    );
    expect(screen.queryByText("Something broke.")).not.toBeInTheDocument();
  });
});
