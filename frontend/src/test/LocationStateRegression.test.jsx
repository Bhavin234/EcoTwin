import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import DemoRunner from "../components/layout/DemoRunner";
import { LocationProvider, useLocationContext } from "../context/LocationContext";

/**
 * Regression test for a real bug found during manual browser testing
 * (post-Milestone-8): after "Run EcoTwin Demo" succeeds, every other page
 * (Overview, Resources, Impact, etc.) reads the location from
 * LocationContext, but DemoRunner previously called `POST /api/demo/run`
 * directly and never told LocationContext a location now exists. The
 * shared state stayed stale (empty) until a full page reload re-fetched
 * it from scratch — client-side navigation to another route never
 * recovered on its own. `LocationProvider` sits above the router in
 * App.jsx and is confirmed NOT to remount on navigation, so the bug was
 * never about provider lifecycle — it was a missed refetch/reconciliation
 * after a mutation the context didn't know about.
 *
 * This test exercises the real `LocationProvider` (not a mock) alongside
 * `DemoRunner`, and a small consumer component that surfaces the current
 * `selectedLocation` the way every real page does — proving the fix
 * without needing a full multi-page React Router integration test, which
 * isn't practical with this project's existing component-test setup
 * (pages are tested individually against a mocked `fetch`, not mounted
 * together under one shared provider in the suite).
 */
function LocationDisplay() {
  const { selectedLocation, loading } = useLocationContext();
  if (loading) return <p>Loading location…</p>;
  if (!selectedLocation) return <p>No location data yet</p>;
  return <p>Monitoring {selectedLocation.name}</p>;
}

const DEMO_RESULT = {
  status: "complete",
  location_id: "loc-demo-1",
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

const LOCATIONS_AFTER_DEMO = [{ id: "loc-demo-1", name: "Greenfield Public School", timezone: "Asia/Kolkata", operating_hours: {} }];

function mockFetch({ startsEmpty }) {
  let locationsCallCount = 0;
  return vi.fn().mockImplementation((url) => {
    if (url.includes("/api/locations")) {
      locationsCallCount += 1;
      const body = startsEmpty && locationsCallCount === 1 ? [] : LOCATIONS_AFTER_DEMO;
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) });
    }
    if (url.includes("/api/demo/run")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(DEMO_RESULT) });
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => "{}" });
  });
}

describe("Location state after Run EcoTwin Demo (regression)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows 'No location data yet' before the demo runs, when the backend genuinely has no locations", async () => {
    global.fetch = mockFetch({ startsEmpty: true });
    render(
      <MemoryRouter>
        <LocationProvider>
          <LocationDisplay />
        </LocationProvider>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("No location data yet")).toBeInTheDocument());
  });

  it("makes the location available immediately after a successful demo run, with no page reload", async () => {
    let resolveDemoRun;
    const demoRunPromise = new Promise((resolve) => {
      resolveDemoRun = resolve;
    });

    let locationsCallCount = 0;
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes("/api/locations")) {
        locationsCallCount += 1;
        // First call (LocationProvider's initial mount): genuinely empty.
        // Every call after: the location the demo created.
        const body = locationsCallCount === 1 ? [] : LOCATIONS_AFTER_DEMO;
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) });
      }
      if (url.includes("/api/demo/run")) {
        // Deliberately held open until we've asserted the "before" state,
        // so this test doesn't race against how fast a mocked promise
        // happens to resolve.
        return demoRunPromise.then(() => ({ ok: true, status: 200, text: async () => JSON.stringify(DEMO_RESULT) }));
      }
      return Promise.resolve({ ok: true, status: 200, text: async () => "{}" });
    });

    render(
      <MemoryRouter>
        <LocationProvider>
          <LocationDisplay />
          <DemoRunner onClose={() => {}} />
        </LocationProvider>
      </MemoryRouter>
    );

    // Before the demo call resolves: genuinely no location yet.
    await waitFor(() => expect(screen.getByText("No location data yet")).toBeInTheDocument());

    // Now let the demo call resolve — LocationContext must reconcile on
    // its own from here, with no page reload. This is the exact behavior
    // that was broken.
    resolveDemoRun();
    await waitFor(() => expect(screen.getByText("Monitoring Greenfield Public School")).toBeInTheDocument(), { timeout: 3000 });
  });

  it("selects the location by the ID the demo actually returned, not just 'first in the list'", async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes("/api/locations")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify([
              { id: "loc-old-duplicate", name: "Greenfield Public School", timezone: "Asia/Kolkata", operating_hours: {} },
              { id: "loc-demo-1", name: "Greenfield Public School", timezone: "Asia/Kolkata", operating_hours: {} },
            ]),
        });
      }
      if (url.includes("/api/demo/run")) {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(DEMO_RESULT) });
      }
      return Promise.resolve({ ok: true, status: 200, text: async () => "{}" });
    });

    function SelectedIdDisplay() {
      const { selectedId, loading } = useLocationContext();
      if (loading) return <p>Loading…</p>;
      return <p>selected: {selectedId}</p>;
    }

    render(
      <MemoryRouter>
        <LocationProvider>
          <SelectedIdDisplay />
          <DemoRunner onClose={() => {}} />
        </LocationProvider>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("selected: loc-demo-1")).toBeInTheDocument(), { timeout: 3000 });
  });
});
