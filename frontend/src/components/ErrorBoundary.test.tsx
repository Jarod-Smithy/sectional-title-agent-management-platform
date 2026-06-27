import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

function Boom(): never {
  throw new Error("kaboom");
}

describe("ErrorBoundary", () => {
  it("renders children when there is no error", () => {
    const report = vi
      .fn()
      .mockResolvedValue({ number: 0, url: "", created: false });
    render(
      <ErrorBoundary report={report}>
        <p>all good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("all good")).toBeInTheDocument();
    expect(report).not.toHaveBeenCalled();
  });

  it("catches a render error, files a report, and links the issue", async () => {
    const report = vi
      .fn()
      .mockResolvedValue({ number: 12, url: "https://gh/12", created: true });
    render(
      <ErrorBoundary report={report}>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(report).toHaveBeenCalledOnce();
    expect(report.mock.calls[0]?.[0]).toMatchObject({ message: "kaboom" });
    expect(
      await screen.findByRole("link", { name: /view the issue/i }),
    ).toHaveAttribute("href", "https://gh/12");
  });
});
