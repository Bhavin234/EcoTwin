# Anomaly Detection (Revised — Multi-Signal)

## Baseline calculation

Unchanged core method: for each `(resource_id, hour_of_day, day_of_week)` slot, compute a rolling mean and standard deviation over a trailing window of comparable slots (default: last 8 comparable weeks). This captures daily and weekly seasonality without requiring a trained model.

```text
baseline_mean(r, h, d)   = mean(consumption)   over last N comparable slots
baseline_stddev(r, h, d) = stddev(consumption) over last N comparable slots
```

## Cold-start behavior

If fewer than a configured minimum number of comparable historical slots exist (default: 3), the slot is marked `insufficient_history` and no anomaly is raised for it — the UI shows "not enough history yet" rather than a fabricated confidence. This is deliberate: the system does not invent confidence where data doesn't support it.

## Multi-signal scoring (this is the key revision)

A single deviation number is not enough — the engine combines multiple signals into a severity decision instead of thresholding one metric:

| Signal | What it measures | How it's used |
|---|---|---|
| **Deviation** | `(current - baseline_mean) / baseline_stddev` (z-score) and `deviation_pct` | Primary magnitude signal |
| **Persistence** | How many consecutive comparable intervals remain elevated | A single elevated reading is downweighted; sustained elevation is upweighted |
| **Operating status** | Whether the location is marked open/closed | Elevated consumption during `closed` status is upweighted (strong leak/malfunction signal) |
| **Occupancy** | Reported headcount, if available | Elevated consumption with occupancy ≈ 0 is upweighted; elevated consumption with high occupancy is downweighted (more likely legitimate use) |
| **Day-of-week pattern match** | Whether today's shape resembles this weekday's historical shape | A shape that diverges from the normal weekday curve (e.g., no evening drop-off) is upweighted |
| **Cross-resource correlation** | Whether a related resource shows a simultaneous anomaly | Correlated anomalies across resources shift toward equipment/systemic causes rather than a single-resource explanation |

## Severity levels

Four levels, computed from a weighted combination of the signals above (weights are configuration, not hardcoded magic numbers):

| Severity | Criteria (indicative) |
|---|---|
| **LOW** | Deviation present but short-lived (1 interval), occupancy/operating-status consistent with legitimate use |
| **MEDIUM** | Sustained deviation (2+ intervals) OR deviation during ambiguous occupancy/operating context |
| **HIGH** | Sustained deviation (3+ intervals) AND at least one strong contextual signal (closed building, zero occupancy, or day-of-week pattern break) |
| **CRITICAL** | Sustained deviation AND multiple strong contextual signals in agreement (e.g., closed + zero occupancy + pattern break), or cross-resource correlation indicating a systemic issue |

A single unusual reading never reaches HIGH or CRITICAL on its own — persistence and context are required, which directly addresses the false-positive/alert-fatigue risk called out in `LIMITATIONS.md` (see `LIMITATION_RESOLUTION_MATRIX.md`).

## "Unusual" vs "operationally suspicious"

- **Unusual** — statistically outside the normal range (deviation/z-score threshold crossed), regardless of context. Always computed and shown at the Resources level.
- **Operationally suspicious** — unusual **and** persistent **and** inconsistent with expected operating context (closed/zero-occupancy/pattern-break). Only "operationally suspicious" cases are promoted to a full Investigation with evidence and AI reasoning — this avoids flooding the investigation workflow with statistically-unusual-but-explainable blips (e.g., a legitimate one-off event).

## Evidence packet construction

The same signals that drive severity are packaged verbatim into the evidence list shown to the user and passed to the AI Reasoning Layer (see `AI_ARCHITECTURE.md`) — the evidence is never a separate narrative constructed after the fact, it is the literal signal values that produced the severity classification, so a user can verify the reasoning independently of the AI text.

## Cause hypothesis scoring (deterministic, feeds Investigation Engine)

Each candidate cause (e.g., `plumbing_leak`, `irrigation_left_active`, `metering_anomaly`, `equipment_malfunction`, `occupancy_driven`, `cleaning_activity`) receives a weighted score from the same signal table above, mapped by a documented rule set, e.g.:

- Elevated + closed + zero occupancy + sustained → strongly favors `plumbing_leak` or `equipment_malfunction`
- Elevated + short burst aligned to a known scheduled window → favors `cleaning_activity` or `irrigation_left_active`
- Elevated + high occupancy → favors `occupancy_driven`
- Elevated with erratic/inconsistent magnitude (not flat) → favors `metering_anomaly`

Scores are normalized to a high/medium/low deterministic rating (not a false-precision percentage) and passed to the AI Reasoning Layer as `deterministic_score`; the AI explains and contextualizes these ratings but does not alter them.

## Verification (pre/post intervention) — implemented Milestone 5

Verification asks two separate questions, each with its own comparison (see `app/services/verification_service.py`):

**1. "Does this look normal again?"** — compared against the *ordinary contextual baseline*, using the exact same causal baseline/deviation engine described above (no second methodology, per Milestone 5's explicit requirement). If the post-intervention window's deviation is still ≥ `Z_THRESHOLD_SUFFICIENT`, the result is `no_measurable_improvement`. Otherwise, it looks statistically normal again, and the result is `verified` if the comparison baseline was `sufficient`-confidence *and* the window's operating context (closed/occupied) matches the original anomaly's — or the lower-confidence `improvement_detected` if either of those doesn't hold (limited-confidence baseline, or a context mismatch that could explain the change some other way — docs Milestone 5, requirement #10, "control for normal variation").

**2. "How much did we avoid?"** — compared against the *counterfactual*: the anomalous rate actually observed during the original anomaly window (i.e., what consumption would likely have continued to be without the fix), not the ordinary baseline. A naive post-actual-vs-ordinary-baseline comparison would make "avoided consumption" collapse to ~0 once a leak is fixed (true, but useless as an impact figure); comparing against the counterfactual answers what a user actually wants to know.

**Verification window:** `[marked_complete_at, marked_complete_at + window_hours)`, where `window_hours` is the original anomaly's own `persistence_hours`, bounded to `[3, 24]` hours — a like-for-like comparison length, capped so verification doesn't wait indefinitely.

**States** (`app/models/intervention.py`, `VerificationStatus`):

| State | Meaning |
|---|---|
| `pending` | Not yet evaluated (e.g. intervention not completed yet) |
| `insufficient_data` | Fewer than 2 post-intervention measurements, or no usable baseline for the window's time slots yet |
| `no_measurable_improvement` | Post-intervention consumption is still statistically elevated |
| `improvement_detected` | Looks normal again, but with lower confidence (limited baseline and/or a context mismatch) |
| `verified` | Looks normal again, backed by a sufficient-confidence baseline and matching operating context |

`insufficient_data` and `no_measurable_improvement` never produce a `verified`-kind `ImpactRecord` — see `DATA_MODEL.md`. Verified against real (dishonestly early) completion timestamps: completing an intervention *during* the still-active leak window correctly produces `no_measurable_improvement`, not a false positive — see `TESTING.md`.

## Implementation notes (Milestone 3)

**Severity scoring is a documented point system**, not the qualitative table above alone — see `app/analytics/severity.py` for the exact, commented implementation:

- **Deviation points (0-3):** based on `max(|z_score|)` within the window: <2.0 → 0, 2.0-3.5 → 1, 3.5-6.0 → 2, ≥6.0 → 3.
- **Persistence points (0-2):** 1 reading → 0, 2-3 readings → 1, 4+ readings → 2.
- **Context points (0-3):** +1 if the window was majority-`closed`, +1 if majority-zero-occupancy, +1 if the *other* resource at the same location also flagged an overlapping window **and** occupancy was zero (cross-resource correlation is only treated as suspicious when occupancy doesn't already explain it — two resources moving together during a busy, fully-occupied period is not on its own evidence of a problem).
- **Severity:** total points 0-1 → LOW, 2-3 → MEDIUM, 4-6 → HIGH, 7-8 → CRITICAL.
- **Classification:** `operationally_suspicious` requires persistence points ≥1 **and** context points ≥1 — both persistence and inconsistent context are required together, exactly as this document specifies. A large but brief and/or fully-occupied deviation can still reach an elevated *severity* score from magnitude alone, but stays classified `unusual` and is not promoted to a full Investigation.

**Cold-start and flagging, clarified from implementation:** a `limited`-state baseline (resource-wide fallback, used when a specific hour/weekday slot doesn't have 3+ prior comparable samples yet, but the resource has some history) is computed and can be shown, but **never flags an anomaly on its own**. A resource-wide baseline blends every hour together, which is a poor predictor for any single hour on a resource with a strong diurnal swing (e.g. electricity's closed-standby vs. daytime-peak swing) — using it to flag anomalies flooded the early "cold start" weeks of the demo dataset with spurious alerts during development testing, which is exactly the false-positive problem this document is meant to prevent. Only a `sufficient`-state baseline (3+ same-hour/same-weekday prior samples) can flag an anomaly. This was caught and fixed by inspecting real output against the Greenfield Public School dataset, not merely by passing unit tests — see `TESTING.md`.

**Baselines are computed causally**, not from the full dataset at once: each measurement's baseline uses only measurements strictly before it (up to the last 8 comparable slots). This was a deliberate implementation choice to prevent an anomaly from diluting its own baseline — since the demo dataset already contains injected anomalies, computing baselines from the full dataset (including the anomalous readings themselves) would have partially hidden them.

**Verified against the actual Greenfield Public School dataset** (10 weeks, `post_intervention_recovery` scenario): the injected water leak (Wednesday of the final week, 18:00-21:00) is independently discovered by the engine — not asserted by the simulator — as a single HIGH-severity, `operationally_suspicious` anomaly with `plumbing_leak` as the top candidate cause, and zero false `operationally_suspicious` classifications anywhere else in either resource's 10-week history.
