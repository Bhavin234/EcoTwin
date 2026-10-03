"""Tests for CSV validation (docs Milestone 2, requirement #8/#13)."""
import pytest

from app.ingestion.csv_source import CSVValidationError, parse_and_validate_csv
from app.models.measurement import MeasurementSource
from app.models.resource import ResourceType

VALID_CSV = (
    "timestamp,location,resource_type,consumption,occupancy,operating_status\n"
    "2026-06-01T08:00:00Z,Test School,electricity,12.5,10,open\n"
    "2026-06-01T09:00:00Z,Test School,electricity,15.0,20,open\n"
    "2026-06-01T08:00:00Z,Test School,water,5.2,10,open\n"
)


def test_valid_csv_is_accepted():
    rows = parse_and_validate_csv(VALID_CSV.encode())
    assert len(rows) == 3
    assert rows[0].location == "Test School"
    assert rows[0].resource_type == ResourceType.ELECTRICITY
    assert rows[0].measurement.source == MeasurementSource.CSV
    assert rows[0].measurement.consumption == 12.5
    assert rows[0].measurement.occupancy == 10


def test_optional_columns_can_be_omitted():
    minimal_csv = "timestamp,location,resource_type,consumption\n2026-06-01T08:00:00Z,Test School,water,5.0\n"
    rows = parse_and_validate_csv(minimal_csv.encode())
    assert len(rows) == 1
    assert rows[0].measurement.occupancy is None


def test_empty_file_is_rejected():
    with pytest.raises(CSVValidationError, match="empty"):
        parse_and_validate_csv(b"")


def test_header_only_file_is_rejected():
    with pytest.raises(CSVValidationError, match="no data rows"):
        parse_and_validate_csv(b"timestamp,location,resource_type,consumption\n")


def test_missing_required_column_is_rejected():
    csv_missing_resource_type = "timestamp,location,consumption\n2026-06-01T08:00:00Z,Test School,5.0\n"
    with pytest.raises(CSVValidationError, match="Missing required column"):
        parse_and_validate_csv(csv_missing_resource_type.encode())


def test_invalid_timestamp_is_rejected():
    bad_csv = "timestamp,location,resource_type,consumption\nnot-a-date,Test School,water,5.0\n"
    with pytest.raises(CSVValidationError) as exc_info:
        parse_and_validate_csv(bad_csv.encode())
    assert any("timestamp" in e for e in exc_info.value.errors)


def test_invalid_resource_type_is_rejected():
    bad_csv = "timestamp,location,resource_type,consumption\n2026-06-01T08:00:00Z,Test School,gas,5.0\n"
    with pytest.raises(CSVValidationError) as exc_info:
        parse_and_validate_csv(bad_csv.encode())
    assert any("resource_type" in e for e in exc_info.value.errors)


def test_negative_consumption_is_rejected():
    bad_csv = "timestamp,location,resource_type,consumption\n2026-06-01T08:00:00Z,Test School,water,-5.0\n"
    with pytest.raises(CSVValidationError) as exc_info:
        parse_and_validate_csv(bad_csv.encode())
    assert any("cannot be negative" in e for e in exc_info.value.errors)


def test_non_numeric_consumption_is_rejected():
    bad_csv = "timestamp,location,resource_type,consumption\n2026-06-01T08:00:00Z,Test School,water,abc\n"
    with pytest.raises(CSVValidationError) as exc_info:
        parse_and_validate_csv(bad_csv.encode())
    assert any("numeric" in e for e in exc_info.value.errors)


def test_mismatched_unit_is_rejected():
    bad_csv = "timestamp,location,resource_type,consumption,unit\n2026-06-01T08:00:00Z,Test School,water,5.0,kWh\n"
    with pytest.raises(CSVValidationError) as exc_info:
        parse_and_validate_csv(bad_csv.encode())
    assert any("unit" in e for e in exc_info.value.errors)


def test_duplicate_row_within_file_is_rejected():
    dup_csv = (
        "timestamp,location,resource_type,consumption\n"
        "2026-06-01T08:00:00Z,Test School,water,5.0\n"
        "2026-06-01T08:00:00Z,Test School,water,6.0\n"
    )
    with pytest.raises(CSVValidationError) as exc_info:
        parse_and_validate_csv(dup_csv.encode())
    assert any("duplicate" in e.lower() for e in exc_info.value.errors)


def test_multiple_errors_are_all_reported_together():
    multi_bad_csv = (
        "timestamp,location,resource_type,consumption\n"
        "not-a-date,Test School,water,5.0\n"
        "2026-06-01T09:00:00Z,,electricity,-3.0\n"
    )
    with pytest.raises(CSVValidationError) as exc_info:
        parse_and_validate_csv(multi_bad_csv.encode())
    # Both rows' problems should surface, not just the first one found.
    assert len(exc_info.value.errors) >= 2
