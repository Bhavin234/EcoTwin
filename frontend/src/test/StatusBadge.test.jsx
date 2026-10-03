import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StatusBadge from "../components/common/StatusBadge";

describe("StatusBadge", () => {
  it("renders a text label, not just a color", () => {
    render(<StatusBadge value="high" />);
    expect(screen.getByText(/high/i)).toBeInTheDocument();
  });

  it("supports a custom label override", () => {
    render(<StatusBadge value="verified" label="All Clear" />);
    expect(screen.getByText("All Clear")).toBeInTheDocument();
  });

  it("falls back to neutral tone for an unknown value without crashing", () => {
    render(<StatusBadge value="totally_unknown_value" />);
    expect(screen.getByText(/totally unknown value/i)).toBeInTheDocument();
  });
});
