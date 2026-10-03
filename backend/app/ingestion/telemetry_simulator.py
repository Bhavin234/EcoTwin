"""
Deterministic telemetry simulator.

Generates realistic hourly electricity and water consumption for a single
location, driven by a configurable `SimulatorConfig` rather than one giant
hardcoded function (docs Milestone 2 requirement #15, "keep the data
generator configurable"). The same `(config, seed)` pair always produces
the same output — required for a reproducible demo (docs/DEMO.md) and for
tests.

This module produces *plausible baseline behavior only* (daily/weekly
patterns, occupancy, noise, gradual trend). Scenario-specific anomalies
(leak, overconsumption, legitimate spike, etc.) are layered on top by
`scenarios.py` — this module never decides what is or isn't an anomaly
(docs Milestone 2 requirement #7).

IMPORTANT: this is a deterministic, seeded *development/demo* telemetry
source — not real sensor data, and not claimed to be. It exists so the
rest of the application (analytics, AI reasoning, intervention/
verification, and the frontend) can be built and demonstrated against
realistic-shaped data before real hardware exists. It writes to the exact
same `measurements` table, in the exact same shape (see
`app/ingestion/schemas.py`, `NormalizedMeasurement`), that a real smart
meter, IoT sensor, or BMS feed would use — so replacing this source with
a real one later requires no change to anything downstream of ingestion
(see `ARCHITECTURE.md`, "Ingestion abstraction").
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.models.measurement import OperatingStatus
from app.models.resource import ResourceType

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass
class OperatingHours:
    """Weekly operating schedule. A day mapped to `None` means closed all day."""

    schedule: dict[str, tuple[float, float] | None] = field(
        default_factory=lambda: {
            "mon": (8.0, 18.0),
            "tue": (8.0, 18.0),
            "wed": (8.0, 18.0),
            "thu": (8.0, 18.0),
            "fri": (8.0, 18.0),
            "sat": None,
            "sun": None,
        }
    )

    def window_for(self, weekday_index: int) -> tuple[float, float] | None:
        """weekday_index: 0=Monday .. 6=Sunday (Python's datetime.weekday())."""
        return self.schedule[WEEKDAY_NAMES[weekday_index]]

    def as_json(self) -> dict:
        """JSON-serializable form, suitable for `Location.operating_hours`."""
        return {
            day: (list(window) if window is not None else None) for day, window in self.schedule.items()
        }


@dataclass
class ResourceProfile:
    """Consumption envelope for one resource type."""

    closed_base: float  # typical consumption while closed/off-hours (standby load)
    open_peak: float  # typical peak consumption during operating hours
    noise_level: float = 0.06  # relative stddev of noise, as a fraction of the local mean
    trend_pct_over_period: float = 0.03  # gradual drift from start to end of the period


@dataclass
class SimulatorConfig:
    """All knobs needed to (re)generate one location's baseline telemetry."""

    seed: int = 42
    start_date: date = date(2026, 6, 1)  # a Monday
    weeks: int = 10
    resolution_minutes: int = 60
    operating_hours: OperatingHours = field(default_factory=OperatingHours)
    profiles: dict[ResourceType, ResourceProfile] = field(
        default_factory=lambda: {
            ResourceType.ELECTRICITY: ResourceProfile(closed_base=4.0, open_peak=45.0, noise_level=0.05, trend_pct_over_period=0.03),
            ResourceType.WATER: ResourceProfile(closed_base=1.0, open_peak=20.0, noise_level=0.08, trend_pct_over_period=0.02),
        }
    )
    base_occupancy_capacity: int = 120  # people at full occupancy

    @property
    def end_date(self) -> date:
        return self.start_date + timedelta(weeks=self.weeks)


def _timestamps(config: SimulatorConfig) -> list[datetime]:
    """Hourly (or configured resolution) UTC timestamps across the period.

    Timestamps are treated as UTC for simplicity in this MVP simulator; a
    Location's `timezone` field exists for real deployments where local
    time actually matters for baseline slot alignment.
    """
    step = timedelta(minutes=config.resolution_minutes)
    start = datetime.combine(config.start_date, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(config.end_date, datetime.min.time(), tzinfo=timezone.utc)
    n_steps = int((end - start) / step)
    return [start + i * step for i in range(n_steps)]


def _occupancy_fraction(hour: float, window: tuple[float, float] | None) -> float:
    """Smooth 0..1 curve: ramps up after opening, peaks mid-window, ramps down before close."""
    if window is None:
        return 0.0
    open_hour, close_hour = window
    if hour < open_hour or hour >= close_hour:
        return 0.0
    span = close_hour - open_hour
    x = (hour - open_hour) / span
    # sin^0.7 gives a rounded ramp-up/ramp-down shape rather than a sharp
    # rectangular block, which is what makes the curve look plausible
    # rather than a step function.
    return max(0.0, math.sin(math.pi * x)) ** 0.7


def _trend_multiplier(day_index: int, total_days: int, trend_pct_over_period: float) -> float:
    """Linear drift across the whole period, centered so the midpoint is unchanged."""
    if total_days <= 1:
        return 1.0
    progress = day_index / (total_days - 1)  # 0..1
    return 1.0 + trend_pct_over_period * (progress - 0.5) * 2


def generate_baseline(config: SimulatorConfig, resource_type: ResourceType) -> pd.DataFrame:
    """
    Generate plausible baseline telemetry for one resource type over the
    whole configured period.

    Returns a DataFrame with columns: timestamp, consumption, occupancy,
    operating_status.
    """
    profile = config.profiles[resource_type]
    timestamps = _timestamps(config)
    total_days = (config.end_date - config.start_date).days

    # Separate, resource-specific RNG stream so electricity and water noise
    # are independent but each fully reproducible from the same seed.
    #
    # IMPORTANT: this must be a stable offset, not Python's built-in
    # hash(str) — string hashing is randomized per-process by default
    # (PYTHONHASHSEED), so hash("water") differs across separate runs of
    # the same program even with identical input. That would silently
    # break the "same seed always produces the same dataset" guarantee
    # across process restarts (it would still look deterministic *within*
    # one run, which is why this needs a comment: it's easy to miss in
    # testing). zlib.crc32 is not affected by hash randomization.
    seed_offset = zlib.crc32(resource_type.value.encode()) % 10_000
    rng = np.random.default_rng(config.seed + seed_offset)

    rows = []
    for ts in timestamps:
        weekday = ts.weekday()
        hour = ts.hour + ts.minute / 60.0
        window = config.operating_hours.window_for(weekday)
        occ_fraction = _occupancy_fraction(hour, window)
        is_operating = window is not None and window[0] <= hour < window[1]
        operating_status = OperatingStatus.OPEN if is_operating else OperatingStatus.CLOSED

        occupancy = int(round(config.base_occupancy_capacity * occ_fraction * (1 + rng.normal(0, 0.05))))
        occupancy = max(0, occupancy)

        day_index = (ts.date() - config.start_date).days
        trend = _trend_multiplier(day_index, total_days, profile.trend_pct_over_period)

        base_value = profile.closed_base + (profile.open_peak - profile.closed_base) * occ_fraction
        noisy_value = base_value * trend * (1 + rng.normal(0, profile.noise_level))
        consumption = max(0.0, round(noisy_value, 3))

        rows.append(
            {
                "timestamp": ts,
                "consumption": consumption,
                "occupancy": occupancy,
                "operating_status": operating_status,
            }
        )

    return pd.DataFrame(rows)



def generate_live_batch(
    start_timestamp: datetime,
    *,
    hours: int = 1,
    seed: int = 42,
) -> dict[ResourceType, pd.DataFrame]:
    """Generate the next simulated telemetry window for a live demo stream.

    This is deliberately separate from ``generate_baseline``: the historical
    simulator creates a reproducible multi-week dataset, while this function
    advances a simulated clock by a small number of hours.  The same
    timestamp/seed pair always produces the same reading, so repeatedly
    calling the endpoint is reproducible and does not depend on process-local
    random state.

    The weekday 18:00-20:00 water pattern is a deterministic *simulated*
    maintenance event.  It is intentionally not written as an anomaly flag;
    the anomaly engine must discover the abnormal consumption/context from
    the measurements themselves.
    """
    if hours < 1 or hours > 24:
        raise ValueError("hours must be between 1 and 24")

    if start_timestamp.tzinfo is None:
        start_timestamp = start_timestamp.replace(tzinfo=timezone.utc)
    else:
        start_timestamp = start_timestamp.astimezone(timezone.utc)

    config = SimulatorConfig(seed=seed)
    timestamps = [start_timestamp + timedelta(hours=i) for i in range(hours)]
    result: dict[ResourceType, pd.DataFrame] = {}

    for resource_type, profile in config.profiles.items():
        rows = []
        for ts in timestamps:
            window = config.operating_hours.window_for(ts.weekday())
            hour = ts.hour + ts.minute / 60.0
            occ_fraction = _occupancy_fraction(hour, window)
            is_operating = window is not None and window[0] <= hour < window[1]
            operating_status = OperatingStatus.OPEN if is_operating else OperatingStatus.CLOSED

            # Stable per-reading RNG: no mutable process state and no Python
            # hash(), so the same timestamp/seed gives the same reading.
            key = f"{resource_type.value}:{ts.isoformat()}".encode()
            seed_offset = zlib.crc32(key) % 1_000_000
            rng = np.random.default_rng(config.seed + seed_offset)

            occupancy = int(round(config.base_occupancy_capacity * occ_fraction * (1 + rng.normal(0, 0.05))))
            occupancy = max(0, occupancy)
            base_value = profile.closed_base + (profile.open_peak - profile.closed_base) * occ_fraction
            noisy_value = base_value * (1 + rng.normal(0, profile.noise_level))
            consumption = max(0.0, round(noisy_value, 3))

            # Every simulated weekday after closing, a two-hour elevated-water
            # pattern appears. It is just telemetry; no anomaly verdict is
            # stored. The deterministic analytics layer must discover it.
            if resource_type == ResourceType.WATER and ts.weekday() < 5 and ts.hour in (18, 19):
                consumption = round(profile.closed_base * 14, 3)
                occupancy = 0
                operating_status = OperatingStatus.CLOSED

            rows.append(
                {
                    "timestamp": ts,
                    "consumption": consumption,
                    "occupancy": occupancy,
                    "operating_status": operating_status,
                }
            )

        result[resource_type] = pd.DataFrame(rows)

    return result
