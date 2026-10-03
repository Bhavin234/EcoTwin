"""
CostFactor / EmissionFactor — the configurable, versioned registry that
cost and CO2e calculations always read from, per docs/EMISSION_CALCULATIONS.md
and the "Emission-factor uncertainty" row of
docs/LIMITATION_RESOLUTION_MATRIX.md. Never hardcode a factor value
elsewhere in the application.
"""
from datetime import date

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.resource import ResourceType


class CostFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cost_factors"

    resource_type: Mapped[ResourceType] = str_enum(ResourceType, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)  # currency per unit
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CostFactor {self.resource_type} {self.rate}{self.currency}>"


class EmissionFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "emission_factors"

    resource_type: Mapped[ResourceType] = str_enum(ResourceType, nullable=False)
    factor_value: Mapped[float] = mapped_column(Float, nullable=False)  # kg CO2e per unit
    unit: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "kg CO2e / kWh" or a longer descriptive label like "kg CO2e / L (embedded/indirect energy estimate)" for water
    source: Mapped[str] = mapped_column(String(255), nullable=False)  # citation
    version: Mapped[str] = mapped_column(String(32), default="v1")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EmissionFactor {self.resource_type} {self.factor_value} ({self.version})>"
