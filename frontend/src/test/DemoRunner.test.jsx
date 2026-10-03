import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import DemoRunner from "../components/layout/DemoRunner";
import { LocationProvider } from "../context/LocationContext";

const DEMO_RESULT = {
  status: "complete",
  location_id: "loc-1",
  location_name: "Greenfield Public School",
  anomaly_id: "anomaly-1",
  resource_type: "water",
  severity: "high",
  explanation_source: "fallback",
  likely_cause: "plumbing_leak",
  deviation_pct: 1299.6,
  z_score: 86.7,
  persistence_hours: 3,
  majority_closed: true,
  majority_zero_occupancy: true,
  recommendation_text: "Inspect fixtures and the incoming water line for continuous flow.",
  intervention_id: "intervention-1",
  verification_status: "verified",
  avoided_consumption: 39.1,
  money_saved: 1.96,
  co2e_avoided_kg: 0.014,
  message: "Post-intervention consumption is back within the normal expected range.",
};

/**
 * URL-aware mock (rather than a simple call-count sequence) since
 * DemoRunner now also talks to LocationContext (`/api/locations`) as part
 * of the location-state regression fix, alongside `/api/demo/run` and
 * `/api/demo/reset` — a plain sequential mock would misinterpret those
 * calls in whatever order they happen to fire.
 */
function mockFetchByUrl({ demoResult = DEMO_RESULT, resetCallback } = {}) {
  return vi.fn().mockImplementation((url) => {
    if (url.includes("/api/locations")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify([{ id: demoResult.location_id || "loc-1", name: "Greenfield Public School", timezone: "Asia/Kolkata", operating_hours: {} }]),
      });
    }
    if (url.includes("/api/demo/reset")) {
      resetCallback?.();
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify({ reset: true, location_name: "Greenfield Public School" }) });
    }
    if (url.includes("/api/demo/run")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(demoResult) });
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => "{}" });
  });
}

function renderDemoRunner() {
  return render(
    <MemoryRouter>
      <LocationProvider>
        <DemoRunner onClose={() => {}} />
      </LocationProvider>
    </MemoryRouter>
  );
}

describe("DemoRunner", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the honest pending step list while the single backend call is in flight, then the real result", async () => {
    global.fetch = mockFetchByUrl();
    renderDemoRunner();

    expect(screen.getByText("Loading telemetry")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText(/plumbing leak/i)).toBeInTheDocument());
    expect(screen.getByText(/1299.6%/)).toBeInTheDocument();
    expect(screen.getByText(/3 hrs/)).toBeInTheDocument();
    expect(screen.getByText("Closed")).toBeInTheDocument();
  });

  it("never claims a fake AI source — reflects fallback honestly via the same status system used elsewhere", async () => {
    global.fetch = mockFetchByUrl();
    renderDemoRunner();
    await waitFor(() => expect(screen.getByText(/plumbing leak/i)).toBeInTheDocument());
    expect(screen.queryByText(/ai reasoning/i)).not.toBeInTheDocument();
  });

  it("shows a reset-and-rerun control that re-invokes the backend", async () => {
    const user = userEvent.setup();
    let resetCalled = false;
    global.fetch = mockFetchByUrl({ resetCallback: () => (resetCalled = true) });
    renderDemoRunner();

    await waitFor(() => expect(screen.getByText(/reset demo and run again/i)).toBeInTheDocument());
    await user.click(screen.getByText(/reset demo and run again/i));
    await waitFor(() => expect(screen.getByText(/plumbing leak/i)).toBeInTheDocument());
    expect(resetCalled).toBe(true);
  });

  it("shows an honest message when no anomaly is found rather than a broken screen", async () => {
    global.fetch = mockFetchByUrl({ demoResult: { status: "no_anomaly_found", location_id: null, location_name: "x", message: "No anomaly found." } });
    renderDemoRunner();
    await waitFor(() => expect(screen.getByText("No anomaly found.")).toBeInTheDocument());
  });
});
