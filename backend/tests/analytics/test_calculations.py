"""Tests for cost/CO2e/savings calculations (docs Milestone 3, requirements #13-15)."""
from datetime import date

from app.analytics.calculations import calculate_co2e, calculate_cost, compute_savings_foundation
from app.models.factors import CostFactor, EmissionFactor
from app.models.resource import ResourceType


def test_calculate_cost_uses_the_given_factor():
    factor = CostFactor(resource_type=ResourceType.ELECTRICITY, rate=8.0, currency="INR", effective_from=date(2026, 1, 1))
    assert calculate_cost(10.0, factor) == 80.0


def test_calculate_co2e_uses_the_given_factor():
    factor = EmissionFactor(
        resource_type=ResourceType.ELECTRICITY, factor_value=0.716, unit="kg CO2e / kWh", source="test", version="v1", effective_from=date(2026, 1, 1)
    )
    assert calculate_co2e(10.0, factor) == 7.16


def test_savings_foundation_excess_when_actual_above_expected():
    result = compute_savings_foundation(expected_consumption=10.0, actual_consumption=25.0)
    assert result.excess_consumption == 15.0
    assert result.avoided_consumption == 0.0


def test_savings_foundation_avoided_when_actual_below_expected():
    result = compute_savings_foundation(expected_consumption=25.0, actual_consumption=10.0)
    assert result.avoided_consumption == 15.0
    assert result.excess_consumption == 0.0


def test_savings_foundation_zero_when_equal():
    result = compute_savings_foundation(expected_consumption=10.0, actual_consumption=10.0)
    assert result.excess_consumption == 0.0
    assert result.avoided_consumption == 0.0
