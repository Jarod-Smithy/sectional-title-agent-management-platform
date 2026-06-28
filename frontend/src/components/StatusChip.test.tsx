import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeverityChip, StatusChip } from "./StatusChip";

describe("StatusChip", () => {
  it("renders the human label for each ticket status", () => {
    const { rerender } = render(<StatusChip status="todo" />);
    expect(screen.getByText("To do")).toBeInTheDocument();
    rerender(<StatusChip status="in_progress" />);
    expect(screen.getByText("In progress")).toBeInTheDocument();
    rerender(<StatusChip status="done" />);
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("renders a plain-English severity label for each guardrail finding", () => {
    const { rerender } = render(<SeverityChip severity="block" />);
    expect(screen.getByText("Must fix")).toBeInTheDocument();
    rerender(<SeverityChip severity="warn" />);
    expect(screen.getByText("Check")).toBeInTheDocument();
    rerender(<SeverityChip severity="info" />);
    expect(screen.getByText("Note")).toBeInTheDocument();
  });
});
