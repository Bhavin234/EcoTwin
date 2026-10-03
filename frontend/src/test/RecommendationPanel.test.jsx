import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RecommendationPanel from "../components/investigations/RecommendationPanel";

describe("RecommendationPanel", () => {
  it("renders the backend action_text verbatim", () => {
    render(
      <RecommendationPanel
        recommendation={{ action_text: "Inspect fixtures and the incoming water line.", priority: "high", estimated_saving: 39.1 }}
        unit="L"
      />
    );
    expect(screen.getByText("Inspect fixtures and the incoming water line.")).toBeInTheDocument();
  });

  it("shows the deterministic estimated saving with its unit", () => {
    render(<RecommendationPanel recommendation={{ action_text: "x", priority: "medium", estimated_saving: 39.1 }} unit="L" />);
    expect(screen.getByText(/39.1 L/)).toBeInTheDocument();
  });

  it("shows an empty state when there is no recommendation yet", () => {
    render(<RecommendationPanel recommendation={null} unit="L" />);
    expect(screen.getByText(/no recommendation yet/i)).toBeInTheDocument();
  });
});
