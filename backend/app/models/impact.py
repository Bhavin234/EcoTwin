"""
ImpactRecord — a savings/impact figure, always tagged with `kind` so
potential, estimated, and verified numbers are never merged into one
undifferentiated "savings" value (docs/DATA_MODEL.md, "Impact terminology";
docs/RELIABILITY_AND_TRUST.md).

Revised in Milestone 5 with two kinds of additions, both additive
(no existing column removed or repurposed):

- `anomaly_id` and `resource_id`: a `potential`/`estimated` record is
  created directly from a detected anomaly, before any intervention
  exists — `intervention_id` alone can't express that. `resource_id` is a
  deliberate denormalization (it's reachable via `anomaly` or via
  `intervention -> recommendation -> investigation -> anomaly`, but
  requiring callers to know which chain applies makes every aggregation
  query — e.g. `GET /api/impact` — needlessly complex) so any impact
  record can be filtered/summed by resource or location directly.
- Factor snapshot columns (`*_factor_value_used`, `*_factor_version`,
  `*_factor_source`, `cost_factor_rate_used`, `cost_factor_currency`):
  preserve exactly which factor values produced this figure, so a later
  edit to the live `cost_factors`/`emission_factors` registry (via
  `PUT /api/config/factors/...`) never silently changes a historical
  impact record's meaning (docs Milestone 5, requirement #14).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class ImpactKind(str, enum.Enum):
    POTENTIAL = "potential"
    ESTIMATED = "estimated"
    VERIFIED = "verified"


class ImpactRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "impact_records"

    intervention_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("interventions.id"), nullable=True)
    anomaly_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("anomalies.id"), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("resources.id"), nullable=True)

    kind: Mapped[ImpactKind] = str_enum(ImpactKind, nullable=False)

    water_saved: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy_saved: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2e_avoided_kg: Mapped[float] = mapped_column(Float, default=0.0)
    money_saved: Mapped[float] = mapped_column(Float, default=0.0)

    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Factor snapshot — see module docstring.
    emission_factor_value_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    emission_factor_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    emission_factor_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost_factor_rate_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_factor_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    intervention: Mapped["Intervention | None"] = relationship(back_populates="impact_records")
    anomaly: Mapped["Anomaly | None"] = relationship()
    resource: Mapped["Resource | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImpactRecord {self.kind} money_saved={self.money_saved}>"
