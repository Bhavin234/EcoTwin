import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InvestigationDetail from "../pages/InvestigationDetail";
import { makeAnomalyDetail, mockFetchJson } from "./mocks";

describe("InvestigationDetail page (integration, mocked backend)", () => {
  beforeEach(() => {
    global.fetch = mockFetchJson(makeAnomalyDetail());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function renderPage() {
    return render(
      <MemoryRouter initialEntries={["/investigations/anomaly-1"]}>
        <Routes>
          <Route path="/investigations/:anomalyId" element={<InvestigationDetail />} />
        </Routes>
      </MemoryRouter>
    );
  }

  it("loads and displays the anomaly, evidence, investigation, and recommendation from the backend", async () => {
    renderPage();

    await waitFor(() => expect(screen.getAllByText("Plumbing Leak").length).toBeGreaterThan(0));

    // Evidence is prominent, not hidden.
    expect(screen.getAllByText(/1300% above the expected baseline/).length).toBeGreaterThan(0);

    // Honest fallback disclosure.
    expect(screen.getAllByText(/deterministic fallback/i).length).toBeGreaterThan(0);

    // Recommendation section uses the backend's action text verbatim.
    expect(screen.getAllByText("Inspect fixtures and the incoming water line for continuous flow.").length).toBeGreaterThan(0);

    // No intervention yet -> the create-intervention prompt should show.
    expect(screen.getByText(/no intervention recorded yet/i)).toBeInTheDocument();
  });

  it("shows an error state if the backend is unreachable", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down"));
    renderPage();
    await waitFor(() => expect(screen.getByText(/could not load this investigation/i)).toBeInTheDocument());
  });
});
