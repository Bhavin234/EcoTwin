"""
CSV telemetry ingestion.

Validates an uploaded CSV completely before anything is inserted
(all-or-nothing) so bad data is never silently accepted (docs Milestone 2,
requirement #8/#12). Every row error is collected and returned together so
the caller can fix the whole file in one pass rather than discovering
errors one row at a time.

Expected columns:
    timestamp       required, ISO-8601 parsable datetime
    location        required, non-empty string (auto-creates the Location if new)
    resource_type   required, one of "electricity" | "water"
    consumption     required, numeric, >= 0
    occupancy       optional, integer >= 0
    operating_status optional, one of "open" | "closed" | "unknown" (default "unknown")
    unit            optional; if present must match the resource type's expected unit
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd

from app.ingestion.schemas import NormalizedMeasurement
from app.models.measurement import MeasurementSource, OperatingStatus
from app.models.resource import ResourceType

REQUIRED_COLUMNS = {"timestamp", "location", "resource_type", "consumption"}
OPTIONAL_COLUMNS = {"occupancy", "operating_status", "unit"}
EXPECTED_UNIT = {ResourceType.ELECTRICITY: "kWh", ResourceType.WATER: "L"}


class CSVValidationError(Exception):
    """Raised when a CSV fails validation. Carries every error found, not just the first."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s): " + "; ".join(errors[:5]))


@dataclass
class ParsedCSVRow:
    location: str
    resource_type: ResourceType
    measurement: NormalizedMeasurement


def parse_and_validate_csv(file_bytes: bytes) -> list[ParsedCSVRow]:
    """
    Parse and fully validate a CSV file's bytes.

    Returns the list of validated rows on success, or raises
    `CSVValidationError` with every problem found (row-numbered, 1-indexed
    including the header row) if any row is invalid. Nothing is partially
    accepted.
    """
    errors: list[str] = []

    if not file_bytes or not file_bytes.strip():
        raise CSVValidationError(["The uploaded file is empty."])

    try:
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    except Exception as exc:  # pragma: no cover - pandas raises many specific error types
        raise CSVValidationError([f"Could not parse file as CSV: {exc}"]) from exc

    if df.empty:
        raise CSVValidationError(["The CSV has a header row but no data rows."])

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise CSVValidationError(
            [f"Missing required column(s): {', '.join(sorted(missing_columns))}"]
        )

    parsed_rows: list[ParsedCSVRow] = []
    seen_in_file: set[tuple[str, str]] = set()  # (location, resource_type) -> timestamps, for in-file duplicate detection

    for i, raw in enumerate(df.to_dict(orient="records")):
        row_number = i + 2  # account for header row, 1-indexed
        row_errors: list[str] = []

        timestamp = None
        raw_timestamp = raw.get("timestamp", "").strip()
        if not raw_timestamp:
            row_errors.append(f"Row {row_number}: 'timestamp' is required.")
        else:
            try:
                timestamp = pd.to_datetime(raw_timestamp, utc=True).to_pydatetime()
            except Exception:
                row_errors.append(f"Row {row_number}: invalid timestamp '{raw_timestamp}'.")

        location = raw.get("location", "").strip()
        if not location:
            row_errors.append(f"Row {row_number}: 'location' is required.")

        resource_type = None
        raw_resource_type = raw.get("resource_type", "").strip().lower()
        if raw_resource_type not in {rt.value for rt in ResourceType}:
            row_errors.append(
                f"Row {row_number}: invalid resource_type '{raw_resource_type}'. "
                f"Must be one of: {', '.join(rt.value for rt in ResourceType)}."
            )
        else:
            resource_type = ResourceType(raw_resource_type)

        consumption = None
        raw_consumption = raw.get("consumption", "").strip()
        try:
            consumption = float(raw_consumption)
            if consumption < 0:
                row_errors.append(f"Row {row_number}: 'consumption' cannot be negative ({consumption}).")
        except ValueError:
            row_errors.append(f"Row {row_number}: 'consumption' must be numeric, got '{raw_consumption}'.")

        occupancy = None
        raw_occupancy = raw.get("occupancy", "").strip()
        if raw_occupancy:
            try:
                occupancy = int(raw_occupancy)
                if occupancy < 0:
                    row_errors.append(f"Row {row_number}: 'occupancy' cannot be negative ({occupancy}).")
            except ValueError:
                row_errors.append(f"Row {row_number}: 'occupancy' must be an integer, got '{raw_occupancy}'.")

        operating_status = OperatingStatus.UNKNOWN
        raw_status = raw.get("operating_status", "").strip().lower()
        if raw_status:
            try:
                operating_status = OperatingStatus(raw_status)
            except ValueError:
                row_errors.append(
                    f"Row {row_number}: invalid operating_status '{raw_status}'. "
                    f"Must be one of: {', '.join(s.value for s in OperatingStatus)}."
                )

        raw_unit = raw.get("unit", "").strip()
        if raw_unit and resource_type is not None and raw_unit != EXPECTED_UNIT[resource_type]:
            row_errors.append(
                f"Row {row_number}: unit '{raw_unit}' does not match expected unit "
                f"'{EXPECTED_UNIT[resource_type]}' for resource_type '{resource_type.value}'."
            )

        if row_errors:
            errors.extend(row_errors)
            continue

        dedup_key = (location, resource_type.value, timestamp.isoformat())
        if dedup_key in seen_in_file:
            errors.append(
                f"Row {row_number}: duplicate row within this file for {location}/{resource_type.value} at {timestamp.isoformat()}."
            )
            continue
        seen_in_file.add(dedup_key)

        parsed_rows.append(
            ParsedCSVRow(
                location=location,
                resource_type=resource_type,
                measurement=NormalizedMeasurement(
                    timestamp=timestamp,
                    consumption=consumption,
                    occupancy=occupancy,
                    operating_status=operating_status,
                    source=MeasurementSource.CSV,
                    scenario=None,
                ),
            )
        )

    if errors:
        raise CSVValidationError(errors)

    return parsed_rows
