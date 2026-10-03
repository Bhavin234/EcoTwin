import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

/** Generic mock: returns a sensible empty/default response for any endpoint the app might call. */
function genericMockFetch() {
  return vi.fn().mockImplementation((url) => {
    let body = {};
    if (url.includes("/api/locations")) body = [{ id: "loc-1", name: "Greenfield Public School", timezone: "Asia/Kolkata", operating_hours: {} }];
    else if (url.includes("/api/resources")) body = [];
    else if (url.includes("/api/anomalies")) body = [];
    else if (url.includes("/api/impact")) body = { summary: [], records: [] };
    else if (url.includes("/api/measurements")) body = { items: [], total: 0, limit: 500, offset: 0 };
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) });
  });
}

describe("App", () => {
  beforeEach(() => {
    global.fetch = genericMockFetch();
    window.history.pushState({}, "", "/");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the application shell with all primary navigation items", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText("EcoTwin")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Resources" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Investigations" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Impact" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Data" })).toBeInTheDocument();
  });

  it("shows the Run EcoTwin Demo button in the top bar", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: /run ecotwin demo/i })).toBeInTheDocument());
  });

  it("navigates to the Investigations page", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByRole("link", { name: "Investigations" })).toBeInTheDocument());
    await user.click(screen.getByRole("link", { name: "Investigations" }));
    expect(await screen.findByText("Anomalies requiring investigation")).toBeInTheDocument();
  });

  it("navigates to the Data page and shows the hardware-agnostic messaging", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByRole("link", { name: "Data" })).toBeInTheDocument());
    await user.click(screen.getByRole("link", { name: "Data" }));
    expect(await screen.findByText(/hardware-agnostic ingestion/i)).toBeInTheDocument();
  });
});
