"""
Deterministic analytics configuration.

Every threshold used by the baseline, deviation, persistence, and severity
engines lives here, named and documented, rather than being buried as a
magic number inside the calculation code (docs Milestone 3, requirement
#7: "severity must be based on documented rules... a developer should be
able to inspect the code and understand why").
"""
from __future__ import annotations

from app.models.resource import ResourceType

# --- Baseline Engine (docs/ANOMALY_DETECTION.md, "Baseline calculation") ---

# Minimum number of prior comparable (same hour-of-day, same day-of-week)
# samples required before a baseline is considered statistically usable on
# its own ("sufficient"). Below this, we fall back to a coarser
# resource-wide baseline rather than inventing confidence from too little
# data (docs, "Cold-start behavior").
MIN_SAMPLES_SUFFICIENT = 3

# Rolling window size: at most this many of the most recent comparable
# slots are used for the baseline (docs: "last 8 comparable weeks").
ROLLING_WINDOW_SLOTS = 8

# Fallback used when the specific (hour, weekday) slot doesn't have enough
# history yet, but the resource has *some* history overall: minimum
# samples required across all hours/weekdays combined, and how many of the
# most recent such samples to use.
GLOBAL_FALLBACK_MIN_SAMPLES = 3
GLOBAL_FALLBACK_WINDOW = 500

# --- Deviation Engine (docs Milestone 3, requirement #4) ---

# When a baseline's standard deviation is at or near zero (e.g. a resource
# that is almost always exactly the same value during closed hours), a raw
# z-score would explode toward +/-infinity for any tiny absolute change.
# Flooring the standard deviation at a small resource-specific value avoids
# that instability while still allowing genuinely large absolute deviations
# to produce a large z-score.
MIN_STDDEV_FLOOR = {
    ResourceType.ELECTRICITY: 0.5,  # kWh
    ResourceType.WATER: 0.15,  # L
}

# Below this baseline mean, a percentage deviation is not a meaningful
# number (dividing by a near-zero baseline produces a huge, misleading
# percentage) — we report `deviation_pct = None` and rely on the z-score
# and absolute deviation instead, rather than showing a distorted percent.
NEAR_ZERO_MEAN_EPSILON = {
    ResourceType.ELECTRICITY: 0.5,  # kWh
    ResourceType.WATER: 0.15,  # L
}

# --- Anomaly flagging thresholds ---

# A reading is "flagged" (statistically unusual) when |z_score| meets or
# exceeds this. Flagging only ever happens when the baseline state is
# `sufficient` (enough slot-specific history) — a `limited` (resource-wide
# fallback) baseline is still computed and can be shown to the user, but
# deliberately never flags an anomaly on its own. A resource-wide baseline
# blends every hour together, which is a poor predictor for any single
# hour on a resource with a strong diurnal swing (e.g. electricity between
# closed-hours standby and daytime peak) — using it to flag anomalies
# would flood the "cold start" period (before enough same-hour/same-weekday
# history accumulates) with spurious alerts that have nothing to do with
# an actual problem. This matches ANOMALY_DETECTION.md's cold-start intent:
# "no anomaly is raised" without adequate comparable history.
Z_THRESHOLD_SUFFICIENT = 2.0

# --- Persistence (docs Milestone 3, requirement #8) ---

# How many consecutive flagged readings define each persistence tier.
# These map to persistence_points in the severity scoring (see severity.py).
PERSISTENCE_POINTS_THRESHOLDS = {
    0: 1,  # a single flagged reading
    1: 2,  # 2-3 consecutive flagged readings
    2: 4,  # 4+ consecutive flagged readings
}

# Consecutive flagged readings at most this far apart (in measurement
# intervals) are still considered one continuous anomaly window, so one
# missing/borderline reading in the middle of a real incident doesn't
# artificially split it into two windows.
MAX_GAP_INTERVALS_TO_MERGE = 1
