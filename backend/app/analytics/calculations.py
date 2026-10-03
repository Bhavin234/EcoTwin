"""
Cost, CO2e, and savings-foundation calculations (docs Milestone 3,
requirements #13-15; docs/EMISSION_CALCULATIONS.md).

Every calculation here is `consumption × factor`, where the factor always
comes from the `cost_factors` / `emission_factors` registry tables — never
hardcoded inline. See `app/services/factor_service.py` for how the active
factor for a resource type is looked up.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.factors import CostFactor, EmissionFactor


def calculate_cost(consumption: float, cost_factor: CostFactor) -> float:
    """consumption (in the resource's native unit) × configured rate."""
    return round(consumption * cost_factor.rate, 2)


def calculate_co2e(consumption: float, emission_factor: EmissionFactor) -> float:
    """consumption (in the resource's native unit) × configured emission factor, in kg CO2e."""
    return round(consumption * emission_factor.factor_value, 3)


@dataclass(frozen=True)
class SavingsFoundation:
    """
    Reusable building blocks for savings calculations. Not yet wired to the
    intervention workflow (that's Milestone 5) — these are the deterministic
    primitives that workflow will call, so the math is written and tested
    once rather than duplicated later.
    """

    expected_consumption: float
    actual_consumption: float
    excess_consumption: float  # how much *more* than expected was used (wastage), floored at 0
    avoided_consumption: float  # how much *less* than expected was used (a reduction), floored at 0


def compute_savings_foundation(expected_consumption: float, actual_consumption: float) -> SavingsFoundation:
    """
    Compare actual consumption to an expected (baseline) figure over some
    window, and split the difference into "excess" (wastage, when actual >
    expected) and "avoided" (a reduction, when actual < expected) rather
    than a single signed number — the intervention workflow (Milestone 5)
    will use `excess_consumption` for pre-intervention wastage estimates
    and `avoided_consumption` for post-intervention savings, and this
    function deliberately does not decide which one applies; the caller's
    context (before or after an intervention) does.
    """
    difference = actual_consumption - expected_consumption
    return SavingsFoundation(
        expected_consumption=expected_consumption,
        actual_consumption=actual_consumption,
        excess_consumption=max(0.0, difference),
        avoided_consumption=max(0.0, -difference),
    )
