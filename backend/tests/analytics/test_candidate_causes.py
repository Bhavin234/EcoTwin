"""Tests for deterministic candidate-cause generation (docs Milestone 3, requirement #10)."""
from app.analytics.candidate_causes import generate_candidate_causes
from app.analytics.severity import ContextSignals
from app.models.resource import ResourceType


def test_water_closed_unoccupied_sustained_favors_plumbing_leak():
    context = ContextSignals(max_abs_z_score=6.0, persistence_count=3, majority_closed=True, majority_zero_occupancy=True, cross_resource_correlated=False)
    causes = generate_candidate_causes(ResourceType.WATER, context)
    assert causes[0]["cause"] == "plumbing_leak"
    assert causes[0]["deterministic_score"] == "high"


def test_water_occupied_favors_occupancy_driven():
    context = ContextSignals(max_abs_z_score=4.0, persistence_count=2, majority_closed=False, majority_zero_occupancy=False, cross_resource_correlated=False)
    causes = generate_candidate_causes(ResourceType.WATER, context)
    assert causes[0]["cause"] == "occupancy_driven"


def test_electricity_closed_unoccupied_sustained_favors_equipment_left_on():
    context = ContextSignals(max_abs_z_score=6.0, persistence_count=4, majority_closed=True, majority_zero_occupancy=True, cross_resource_correlated=False)
    causes = generate_candidate_causes(ResourceType.ELECTRICITY, context)
    assert causes[0]["cause"] == "equipment_left_on"
    assert causes[0]["deterministic_score"] == "high"


def test_every_cause_list_includes_metering_anomaly_as_a_low_confidence_option():
    context = ContextSignals(max_abs_z_score=3.0, persistence_count=1, majority_closed=False, majority_zero_occupancy=True, cross_resource_correlated=False)
    for resource_type in (ResourceType.WATER, ResourceType.ELECTRICITY):
        causes = generate_candidate_causes(resource_type, context)
        metering = next(c for c in causes if c["cause"] == "metering_anomaly")
        assert metering["deterministic_score"] == "low"
