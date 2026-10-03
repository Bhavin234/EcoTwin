import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AIInvestigationPanel from "../components/investigations/AIInvestigationPanel";
import { makeAnomalyDetail } from "./mocks";

describe("AIInvestigationPanel", () => {
  it("honestly labels a fallback investigation as deterministic fallback, never as AI", () => {
    const { investigation } = makeAnomalyDetail();
    render(<AIInvestigationPanel investigation={investigation} />);
    expect(screen.getAllByText(/deterministic fallback/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/investigation engine: ai reasoning/i)).not.toBeInTheDocument();
  });

  it("labels an AI-sourced investigation as AI reasoning", () => {
    const { investigation } = makeAnomalyDetail({
      investigation: { ...makeAnomalyDetail().investigation, explanation_source: "ai" },
    });
    render(<AIInvestigationPanel investigation={investigation} />);
    expect(screen.getByText(/investigation engine: ai reasoning/i)).toBeInTheDocument();
  });

  it("renders observed facts and inference as visually distinct sections", () => {
    const { investigation } = makeAnomalyDetail();
    render(<AIInvestigationPanel investigation={investigation} />);
    expect(screen.getByText("Observed")).toBeInTheDocument();
    expect(screen.getByText("Inference")).toBeInTheDocument();
    expect(screen.getByText(/sustained elevated flow while closed/i)).toBeInTheDocument();
  });

  it("renders alternative explanations", () => {
    const { investigation } = makeAnomalyDetail();
    render(<AIInvestigationPanel investigation={investigation} />);
    expect(screen.getByText(/irrigation left active/i)).toBeInTheDocument();
  });

  it("shows a not-yet-investigated message when there is no explanation", () => {
    const { investigation } = makeAnomalyDetail({
      investigation: { ...makeAnomalyDetail().investigation, explanation: null },
    });
    render(<AIInvestigationPanel investigation={investigation} />);
    expect(screen.getByText(/not yet investigated/i)).toBeInTheDocument();
  });
});
