"""
Tests for each of the six named scenarios (docs/DEMO.md, Milestone 2
requirement #4/#13): each should exhibit the specific, realistic pattern it
claims to, not just "some numbers changed somewhere."
"""
from datetime import timedelta

from app.ingestion.scenarios import generate_scenario
from app.ingestion.telemetry_simulator import SimulatorConfig
from app.models.measurement import OperatingStatus
from app.models.resource import ResourceType


def _config():
    from datetime import date

    return SimulatorConfig(seed=42, start_date=date(2026, 6, 1), weeks=5)


def test_normal_operation_has_no_injected_window():
    result = generate_scenario("normal_operation", _config())
    assert result.reference_windows == []


def test_water_leak_is_sustained_and_flat_not_a_single_spike():
    result = generate_scenario("water_leak", _config())
    window = result.reference_windows[0]
    df = result.measurements[ResourceType.WATER]

    within_window = df[(df["timestamp"] >= window.start) & (df["timestamp"] < window.end)]
    # Sustained for multiple consecutive hourly readings, not one row.
    assert len(within_window) >= 3
    # Flat: low variance across the injected window (a leak is a
    # continuous flow, not a fluctuating pattern).
    assert within_window["consumption"].std() < 0.5
    # Building must be closed and unoccupied throughout the anomaly.
    assert (within_window["operating_status"] == OperatingStatus.CLOSED).all()
    assert (within_window["occupancy"] == 0).all()

    # And it must be clearly elevated relative to the resource's known
    # closed-hours standby baseline (not the hours immediately before,
    # which are still ramping down from the operating-hours peak).
    closed_base = _config().profiles[ResourceType.WATER].closed_base
    assert within_window["consumption"].mean() > closed_base * 3


def test_electricity_overconsumption_persists_after_hours():
    result = generate_scenario("electricity_overconsumption", _config())
    window = result.reference_windows[0]
    df = result.measurements[ResourceType.ELECTRICITY]

    within_window = df[(df["timestamp"] >= window.start) & (df["timestamp"] < window.end)]
    assert len(within_window) >= 3
    assert (within_window["operating_status"] == OperatingStatus.CLOSED).all()

    profile = _config().profiles[ResourceType.ELECTRICITY]
    # Elevated relative to ordinary closed hours, but should not exceed the
    # normal daytime peak — this must look like leftover load, not an
    # implausible spike.
    assert within_window["consumption"].mean() > profile.closed_base * 1.5
    assert within_window["consumption"].mean() < profile.open_peak


def test_closed_building_consumption_covers_a_full_closed_day():
    result = generate_scenario("closed_building_consumption", _config())
    df_elec = result.measurements[ResourceType.ELECTRICITY]
    window = next(w for w in result.reference_windows if w.resource_type == ResourceType.ELECTRICITY)

    day_rows = df_elec[(df_elec["timestamp"] >= window.start) & (df_elec["timestamp"] < window.end)]
    assert len(day_rows) == 24
    assert (day_rows["operating_status"] == OperatingStatus.CLOSED).all()
    assert (day_rows["occupancy"] == 0).all()
    # Despite being "closed," at least one hour should show meaningfully
    # elevated consumption resembling the weekday daytime pattern.
    assert day_rows["consumption"].max() > day_rows["consumption"].min() * 2


def test_legitimate_spike_is_temporary_and_occupancy_consistent():
    result = generate_scenario("legitimate_spike", _config())
    window = next(w for w in result.reference_windows if w.resource_type == ResourceType.ELECTRICITY)
    df = result.measurements[ResourceType.ELECTRICITY]

    within_window = df[(df["timestamp"] >= window.start) & (df["timestamp"] < window.end)]
    after_window = df[(df["timestamp"] >= window.end) & (df["timestamp"] < window.end + timedelta(hours=3))]

    # Elevated occupancy explains the elevated consumption.
    assert (within_window["occupancy"] > 0).all()
    # And it's genuinely temporary: consumption after the window drops back
    # down, it doesn't stay elevated indefinitely like the leak scenario.
    assert after_window["consumption"].mean() < within_window["consumption"].mean()


def test_post_intervention_recovery_returns_to_baseline_after_the_incident():
    result = generate_scenario("post_intervention_recovery", _config())
    df = result.measurements[ResourceType.WATER]
    leak_window = result.reference_windows[0]
    recovery_window = result.reference_windows[-1]

    leak_rows = df[(df["timestamp"] >= leak_window.start) & (df["timestamp"] < leak_window.end)]
    # Look at closed-hours readings within the recovery window only (the
    # comparison that matters is closed-hours-to-closed-hours).
    recovery_rows = df[
        (df["timestamp"] >= recovery_window.start)
        & (df["timestamp"] < recovery_window.end)
        & (df["operating_status"] == OperatingStatus.CLOSED)
    ]

    assert len(recovery_rows) > 0
    assert recovery_rows["consumption"].mean() < leak_rows["consumption"].mean() / 3


def test_unknown_scenario_name_raises_with_helpful_message():
    import pytest

    with pytest.raises(KeyError, match="Unknown scenario"):
        generate_scenario("not_a_real_scenario", _config())
