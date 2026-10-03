import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MethodologySplit from "../components/investigations/MethodologySplit";
import { makeAnomalyDetail } from "./mocks";

describe("MethodologySplit", () => {
  it("shows deterministic signals and AI reasoning in separate columns", () => {
    const anomaly = makeAnomalyDetail();
    render(<MethodologySplit anomaly={anomaly} investigation={anomaly.investigation} />);

    expect(screen.getByText("Deterministic analysis")).toBeInTheDocument();
    expect(screen.getByText("AI contextual investigation")).toBeInTheDocument();
    expect(screen.getByText("+1299.6%")).toBeInTheDocument();
    expect(screen.getAllByText(/plumbing leak/i).length).toBeGreaterThan(0);
  });

  it("shows a not-yet-investigated message on the AI side when there is no explanation", () => {
    const anomaly = makeAnomalyDetail({ investigation: { ...makeAnomalyDetail().investigation, explanation: null } });
    render(<MethodologySplit anomaly={anomaly} investigation={anomaly.investigation} />);
    expect(screen.getByText(/not yet investigated/i)).toBeInTheDocument();
  });

  it("reflects the actual operating context signals, not a fixed assumption", () => {
    const anomaly = makeAnomalyDetail({ signals: { majority_closed: false, majority_zero_occupancy: false, persistence_hours: 3, baseline_state: "sufficient" } });
    render(<MethodologySplit anomaly={anomaly} investigation={anomaly.investigation} />);
    expect(screen.getByText(/open/i)).toBeInTheDocument();
    expect(screen.getByText(/present/i)).toBeInTheDocument();
  });
});
