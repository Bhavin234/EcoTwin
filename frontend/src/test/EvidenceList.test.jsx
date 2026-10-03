import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import EvidenceList from "../components/investigations/EvidenceList";

const evidence = [
  { signal: "baseline_deviation", value: 238, unit: "percent", description: "Consumption was 238% above the expected baseline." },
  { signal: "occupancy", value: 0, description: "Recorded occupancy was zero for most of this window." },
];

describe("EvidenceList", () => {
  it("renders every evidence item's description directly (not behind a toggle)", () => {
    render(<EvidenceList evidence={evidence} />);
    expect(screen.getByText(/238% above the expected baseline/)).toBeInTheDocument();
    expect(screen.getByText(/occupancy was zero/i)).toBeInTheDocument();
  });

  it("shows an honest empty state when there is no evidence", () => {
    render(<EvidenceList evidence={[]} />);
    expect(screen.getByText(/no evidence recorded/i)).toBeInTheDocument();
  });

  it("never invents evidence text beyond what was passed in", () => {
    render(<EvidenceList evidence={evidence} />);
    expect(screen.queryByText(/plumbing leak/i)).not.toBeInTheDocument();
  });
});
