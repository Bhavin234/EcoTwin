"""
Cost/emission factor registry service (docs Milestone 3, requirements #13-14;
docs/EMISSION_CALCULATIONS.md).

`ensure_default_factors` seeds one active cost and emission factor per
resource type if none exist yet, so calculations always have something to
read from the registry rather than a hardcoded fallback. The seeded values
are explicitly labeled as illustrative defaults pending a cited, verified
source — see the `source` field on each seeded `EmissionFactor`.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.factors import CostFactor, EmissionFactor
from app.models.resource import ResourceType

# Illustrative defaults only. EMISSION_CALCULATIONS.md is explicit that the
# exact figures and citations should be finalized before any real-world
# (non-demo) use; these values exist so the MVP's calculations have
# something concrete and traceable to compute from on day one.
DEFAULT_COST_FACTORS = {
    ResourceType.ELECTRICITY: 8.0,  # INR per kWh — illustrative Indian commercial tariff
    ResourceType.WATER: 0.05,  # INR per L (~INR 50/kL) — illustrative Indian commercial water tariff
}

DEFAULT_EMISSION_FACTORS = {
    ResourceType.ELECTRICITY: {
        "factor_value": 0.716,  # kg CO2e per kWh
        "unit": "kg CO2e / kWh",
        "source": "Illustrative default modeled on India's CEA CO2 Baseline Database grid emission factor — verify the exact figure and version before non-demo use.",
    },
    ResourceType.WATER: {
        "factor_value": 0.00035,  # kg CO2e per L — embedded pumping/treatment energy proxy
        "unit": "kg CO2e / L (embedded/indirect energy estimate)",
        "source": "Illustrative default for embedded pumping/treatment energy — not a direct emission factor; verify before non-demo use.",
    },
}


def ensure_default_factors(db: Session) -> None:
    """Idempotently seed one default cost and emission factor per resource type."""
    for resource_type, rate in DEFAULT_COST_FACTORS.items():
        existing = db.execute(select(CostFactor).where(CostFactor.resource_type == resource_type)).first()
        if not existing:
            db.add(CostFactor(resource_type=resource_type, rate=rate, currency="INR", effective_from=date(2026, 1, 1)))

    for resource_type, spec in DEFAULT_EMISSION_FACTORS.items():
        existing = db.execute(select(EmissionFactor).where(EmissionFactor.resource_type == resource_type)).first()
        if not existing:
            db.add(
                EmissionFactor(
                    resource_type=resource_type,
                    factor_value=spec["factor_value"],
                    unit=spec["unit"],
                    source=spec["source"],
                    version="v1",
                    effective_from=date(2026, 1, 1),
                )
            )
    db.commit()


def get_active_cost_factor(db: Session, resource_type: ResourceType, as_of: date | None = None) -> CostFactor | None:
    """Most recent cost factor for a resource type effective on or before `as_of` (default: today)."""
    as_of = as_of or date.today()
    return db.execute(
        select(CostFactor)
        .where(CostFactor.resource_type == resource_type, CostFactor.effective_from <= as_of)
        .order_by(CostFactor.effective_from.desc())
    ).scalars().first()


def get_active_emission_factor(db: Session, resource_type: ResourceType, as_of: date | None = None) -> EmissionFactor | None:
    """Most recent emission factor for a resource type effective on or before `as_of` (default: today)."""
    as_of = as_of or date.today()
    return db.execute(
        select(EmissionFactor)
        .where(EmissionFactor.resource_type == resource_type, EmissionFactor.effective_from <= as_of)
        .order_by(EmissionFactor.effective_from.desc())
    ).scalars().first()
