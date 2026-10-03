import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import InvestigationDetail from "../pages/InvestigationDetail";
import { makeAnomalyDetail } from "./mocks";

/**
 * Simulates a browser refresh (docs Milestone 8, requirement #15): a
 * completely fresh component mount, with no prior client-side state,
 * given a backend response that already reflects a completed and verified
 * intervention. The page must recover that state entirely from the
 * backend response — critical workflow state must never live only in
 * volatile React state that a refresh would lose.
 */
describe("Recovery from persisted backend state (browser-refresh equivalent)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows a completed, verified intervention correctly on a fresh mount", async () => {
    const anomalyWithCompletedIntervention = makeAnomalyDetail({
      investigation: {
        ...makeAnomalyDetail().investigation,
        recommendation: {
          ...makeAnomalyDetail().investigation.recommendation,
          intervention: {
            id: "intervention-1",
            recommendation_id: "recommendation-1",
            status: "completed",
            verification_status: "verified",
            marked_complete_at: "2026-08-05T21:00:00",
          },
        },
      },
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(anomalyWithCompletedIntervention),
    });

    render(
      <MemoryRouter initialEntries={["/investigations/anomaly-1"]}>
        <Routes>
          <Route path="/investigations/:anomalyId" element={<InvestigationDetail />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText(/did it work/i)).toBeInTheDocument());
    expect(screen.getAllByText(/completed/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/verified/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/no intervention recorded yet/i)).not.toBeInTheDocument();
  });
});
