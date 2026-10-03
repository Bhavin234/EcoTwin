import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocationProvider } from "../context/LocationContext";
import Overview from "../pages/Overview";
import InvestigationDetail from "../pages/InvestigationDetail";

describe("Frontend failure handling (docs Milestone 8, requirement #14)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows a readable message, not a broken screen, when the backend is completely offline", async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    render(
      <MemoryRouter>
        <LocationProvider>
          <Overview />
        </LocationProvider>
      </MemoryRouter>
    );
    // LocationContext's fetch fails -> selectedLocation stays null -> the
    // page must show a helpful message, not crash or render blank.
    await waitFor(() => expect(screen.getByText(/no location data yet/i)).toBeInTheDocument());
  });

  it("shows an error state (not a raw stack trace) when the backend returns a 500", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => JSON.stringify({ error: { code: "internal_error", message: "An unexpected error occurred. Please try again." } }),
    });
    render(
      <MemoryRouter initialEntries={["/investigations/anomaly-1"]}>
        <Routes>
          <Route path="/investigations/:anomalyId" element={<InvestigationDetail />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText(/could not load this investigation/i)).toBeInTheDocument());
    // The backend's clean message is shown, never a raw traceback.
    expect(screen.getByText(/an unexpected error occurred/i)).toBeInTheDocument();
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument();
  });

  it("handles a malformed (non-JSON) error body without crashing", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      text: async () => "<html>Bad Gateway</html>",
    });
    render(
      <MemoryRouter initialEntries={["/investigations/anomaly-1"]}>
        <Routes>
          <Route path="/investigations/:anomalyId" element={<InvestigationDetail />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText(/could not load this investigation/i)).toBeInTheDocument());
  });

  it("supports a retry action rather than leaving the user stuck", async () => {
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      callCount += 1;
      if (callCount === 1) return Promise.reject(new TypeError("Failed to fetch"));
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify([{ id: "loc-1", name: "Test School", timezone: "Asia/Kolkata", operating_hours: {} }]),
      });
    });
    render(
      <MemoryRouter>
        <LocationProvider>
          <Overview />
        </LocationProvider>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText(/no location data yet/i)).toBeInTheDocument());
  });
});
