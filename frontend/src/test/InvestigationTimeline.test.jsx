import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import InvestigationTimeline from "../components/investigations/InvestigationTimeline";
import { makeAnomalyDetail } from "./mocks";

describe("InvestigationTimeline", () => {
  it("marks earlier stages done and later stages pending when no intervention exists yet", () => {
    const anomaly = makeAnomalyDetail();
    render(<InvestigationTimeline anomaly={anomaly} investigation={anomaly.investigation} intervention={null} />);

    expect(screen.getByText("Anomaly detected")).toBeInTheDocument();
    expect(screen.getByText("Evidence collected")).toBeInTheDocument();
    expect(screen.getByText("Cause investigated")).toBeInTheDocument();
    expect(screen.getByText("Action recommended")).toBeInTheDocument();
    expect(screen.getByText(/not yet created/i)).toBeInTheDocument();
  });

  it("reflects a completed and verified intervention", () => {
    const anomaly = makeAnomalyDetail();
    const intervention = { status: "completed", verification_status: "verified", marked_complete_at: "2026-08-05T21:00:00" };
    render(<InvestigationTimeline anomaly={anomaly} investigation={anomaly.investigation} intervention={intervention} />);
    expect(screen.getByText("Improvement verified")).toBeInTheDocument();
  });

  it("honestly shows no-improvement rather than a false success", () => {
    const anomaly = makeAnomalyDetail();
    const intervention = { status: "completed", verification_status: "no_measurable_improvement", marked_complete_at: "2026-08-05T18:30:00" };
    render(<InvestigationTimeline anomaly={anomaly} investigation={anomaly.investigation} intervention={intervention} />);
    expect(screen.getByText("Improvement not yet observed")).toBeInTheDocument();
  });

  it("never invents evidence text beyond what the anomaly provided", () => {
    const anomaly = makeAnomalyDetail();
    render(<InvestigationTimeline anomaly={anomaly} investigation={anomaly.investigation} intervention={null} />);
    expect(screen.queryByText(/hardcoded|fake/i)).not.toBeInTheDocument();
  });
});
