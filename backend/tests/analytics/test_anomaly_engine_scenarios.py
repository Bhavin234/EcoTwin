"""
Runs the deterministic anomaly engine against the actual Milestone 2
scenario generators (docs Milestone 3, requirements #12/#19) — proving the
engine *discovers* each scenario's injected pattern from the telemetry
itself, since the simulator never writes an anomaly flag (docs Milestone
2, requirement #7 / Milestone 3, requirement #19).
"""
from app.analytics.anomaly_engine import analyze_resource
from app.ingestion.scenarios import generate_scenario
from app.models.resource import ResourceType


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and a_end > b_start


def test_normal_operation_raises_no_operationally_suspicious_anomalies():
    result = generate_scenario("normal_operation")
    for resource_type, df in result.measurements.items():
        _, anomalies, _ = analyze_resource(df, resource_type)
        suspicious = [a for a in anomalies if a.classification == "operationally_suspicious"]
        critical = [a for a in anomalies if a.severity == "critical"]
        assert suspicious == [], f"{resource_type}: normal operation should raise no operationally_suspicious anomalies"
        assert critical == [], f"{resource_type}: normal operation should raise no CRITICAL anomalies"


def test_water_leak_is_discovered_and_classified_operationally_suspicious():
    result = generate_scenario("water_leak")
    leak_window = result.reference_windows[0]
    df = result.measurements[ResourceType.WATER]

    _, anomalies, _ = analyze_resource(df, ResourceType.WATER)
    overlapping = [a for a in anomalies if _overlaps(a.window_start, a.window_end, leak_window.start, leak_window.end)]

    assert overlapping, "the engine should have detected an anomaly overlapping the injected leak window"
    assert any(a.classification == "operationally_suspicious" for a in overlapping)
    assert any(a.severity in ("high", "critical") for a in overlapping)

    # Evidence must reflect the actual context, not a canned string.
    suspicious = next(a for a in overlapping if a.classification == "operationally_suspicious")
    evidence_signals = {e["signal"] for e in suspicious.evidence}
    assert "occupancy" in evidence_signals
    assert "operating_status" in evidence_signals
    assert suspicious.candidate_causes[0]["cause"] == "plumbing_leak"


def test_electricity_overconsumption_is_discovered():
    result = generate_scenario("electricity_overconsumption")
    window = result.reference_windows[0]
    df = result.measurements[ResourceType.ELECTRICITY]

    _, anomalies, _ = analyze_resource(df, ResourceType.ELECTRICITY)
    overlapping = [a for a in anomalies if _overlaps(a.window_start, a.window_end, window.start, window.end)]

    assert overlapping
    assert any(a.classification == "operationally_suspicious" for a in overlapping)


def test_closed_building_consumption_is_strongly_flagged_on_both_resources():
    result = generate_scenario("closed_building_consumption")
    for resource_type, df in result.measurements.items():
        window = next(w for w in result.reference_windows if w.resource_type == resource_type)
        _, anomalies, _ = analyze_resource(df, resource_type)
        overlapping = [a for a in anomalies if _overlaps(a.window_start, a.window_end, window.start, window.end)]
        assert overlapping, f"{resource_type}: should detect the closed-day anomaly"
        assert any(a.classification == "operationally_suspicious" for a in overlapping)


def test_legitimate_spike_is_not_classified_operationally_suspicious():
    """The key false-positive-avoidance test (docs Milestone 3, requirement #12)."""
    result = generate_scenario("legitimate_spike")
    for resource_type, df in result.measurements.items():
        window = next(w for w in result.reference_windows if w.resource_type == resource_type)
        _, anomalies, _ = analyze_resource(df, resource_type)
        overlapping = [a for a in anomalies if _overlaps(a.window_start, a.window_end, window.start, window.end)]
        # It's fine (even expected) for this to show up as a statistically
        # "unusual" anomaly — it must NOT be operationally_suspicious.
        suspicious_overlap = [a for a in overlapping if a.classification == "operationally_suspicious"]
        assert suspicious_overlap == [], (
            f"{resource_type}: a legitimate, occupancy-consistent spike must not be classified operationally_suspicious"
        )


def test_greenfield_demo_story_end_to_end():
    """The exact narrative from docs/DEMO.md, derived by the engine rather than asserted by fiat."""
    result = generate_scenario("post_intervention_recovery")
    leak_window = result.reference_windows[0]
    recovery_window = result.reference_windows[-1]
    df = result.measurements[ResourceType.WATER]

    _, anomalies, _ = analyze_resource(df, ResourceType.WATER)

    leak_anomalies = [a for a in anomalies if _overlaps(a.window_start, a.window_end, leak_window.start, leak_window.end)]
    assert leak_anomalies
    suspicious = [a for a in leak_anomalies if a.classification == "operationally_suspicious"]
    assert suspicious, "Greenfield water leak should be discovered and classified operationally_suspicious"
    assert suspicious[0].severity in ("high", "critical")

    # After the marked recovery window, no further operationally_suspicious
    # anomaly should overlap it — consumption is back to looking ordinary.
    recovery_anomalies = [
        a
        for a in anomalies
        if _overlaps(a.window_start, a.window_end, recovery_window.start, recovery_window.end)
        and a.classification == "operationally_suspicious"
    ]
    assert recovery_anomalies == [], "post-intervention window should not still look operationally suspicious"


def test_reproducibility_same_scenario_produces_identical_anomalies():
    result1 = generate_scenario("water_leak")
    result2 = generate_scenario("water_leak")

    _, anomalies1, _ = analyze_resource(result1.measurements[ResourceType.WATER], ResourceType.WATER)
    _, anomalies2, _ = analyze_resource(result2.measurements[ResourceType.WATER], ResourceType.WATER)

    assert len(anomalies1) == len(anomalies2)
    for a1, a2 in zip(anomalies1, anomalies2):
        assert a1.severity == a2.severity
        assert a1.classification == a2.classification
        assert a1.window_start == a2.window_start
        assert a1.window_end == a2.window_end
