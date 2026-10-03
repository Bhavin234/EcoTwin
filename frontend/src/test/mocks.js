import { vi } from "vitest";

/** Builds a minimal, realistic anomaly detail payload matching the real backend shape. */
export function makeAnomalyDetail(overrides = {}) {
  return {
    id: "anomaly-1",
    resource_id: "resource-water-1",
    resource_type: "water",
    detected_at: "2026-08-05T21:00:00",
    window_start: "2026-08-05T18:00:00",
    window_end: "2026-08-05T21:00:00",
    severity: "high",
    classification: "operationally_suspicious",
    deviation_pct: 1299.6,
    z_score: 86.7,
    status: "open",
    signals: { persistence_hours: 3 },
    evidence: [
      { signal: "baseline_deviation", value: 1299.6, unit: "percent", description: "Consumption was 1300% above the expected baseline." },
      { signal: "occupancy", value: 0, description: "Recorded occupancy was zero for most of this window." },
    ],
    investigation: {
      id: "investigation-1",
      candidate_causes: [
        { cause: "plumbing_leak", deterministic_score: "high" },
        { cause: "irrigation_left_active", deterministic_score: "medium" },
      ],
      top_cause: "plumbing_leak",
      explanation: {
        likely_cause: "plumbing_leak",
        observed: ["Consumption was 1300% above the expected baseline.", "Occupancy was zero."],
        inference: "Sustained elevated flow while closed and unoccupied points to a continuous leak.",
        supporting_evidence: ["baseline_deviation", "occupancy"],
        alternative_explanations: [{ cause: "irrigation_left_active", why_less_likely: "Less consistent with the sustained pattern." }],
        recommended_next_step: "Inspect fixtures and the incoming water line for continuous flow.",
        reasoning_confidence: "high",
      },
      explanation_source: "fallback",
      recommendation: {
        id: "recommendation-1",
        investigation_id: "investigation-1",
        action_text: "Inspect fixtures and the incoming water line for continuous flow.",
        priority: "high",
        estimated_saving: 39.1,
        intervention: null,
      },
    },
    ...overrides,
  };
}

export function mockFetchJson(payload, { ok = true, status = 200 } = {}) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    text: async () => JSON.stringify(payload),
  });
}
