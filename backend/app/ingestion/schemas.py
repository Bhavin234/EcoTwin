"""
Common data contract every ingestion source must produce.

Both the telemetry simulator and CSV upload path normalize their input into
a list of `NormalizedMeasurement` before anything is written to the
database. This is what makes ingestion hardware-agnostic: a future
smart-meter/IoT/BMS source only needs to produce this same shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.measurement import MeasurementSource, OperatingStatus


@dataclass(frozen=True)
class NormalizedMeasurement:
    """One validated telemetry reading, ready to be persisted."""

    timestamp: datetime
    consumption: float
    occupancy: int | None
    operating_status: OperatingStatus
    source: MeasurementSource
    scenario: str | None = None
