"""
Resource — a monitored electricity or water feed at a Location.

Electricity and water intentionally share this single table (see
docs/DATA_MODEL.md, "Design principle") rather than having separate
per-resource-type tables; `resource_type` plus the linked cost/emission
factors are enough to keep the schema generic and extensible.
"""
import enum
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class ResourceType(str, enum.Enum):
    ELECTRICITY = "electricity"
    WATER = "water"
    # Deliberately not implemented for the MVP (see docs/LIMITATIONS.md /
    # docs/FUTURE_SCOPE.md): FUEL = "fuel", WASTE = "waste"


class Resource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resources"

    location_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("locations.id"), nullable=False)
    resource_type: Mapped[ResourceType] = str_enum(ResourceType, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)  # "kWh" | "L"

    cost_factor_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("cost_factors.id"), nullable=True)
    emission_factor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("emission_factors.id"), nullable=True
    )

    location: Mapped["Location"] = relationship(back_populates="resources")
    measurements: Mapped[list["Measurement"]] = relationship(back_populates="resource", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Resource {self.resource_type} @ {self.location_id}>"
