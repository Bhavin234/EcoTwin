"""
Anomaly — a detected deviation, with its full signal/evidence packet
attached. `signals` is the literal data structure used both to display
evidence to the user and to feed the AI Reasoning Layer (or its fallback);
see docs/ANOMALY_DETECTION.md and docs/AI_ARCHITECTURE.md.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyClassification(str, enum.Enum):
    UNUSUAL = "unusual"
    OPERATIONALLY_SUSPICIOUS = "operationally_suspicious"


class AnomalyStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Anomaly(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "anomalies"

    resource_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("resources.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    severity: Mapped[Severity] = str_enum(Severity, nullable=False)
    # Nullable: when the baseline mean is too close to zero for a
    # percentage to be meaningful, this is left null rather than showing a
    # misleading 0% or an exaggerated percentage (see
    # app/analytics/deviation.py). z_score remains valid in that case.
    deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Full signal packet: persistence, operating_status, occupancy,
    # pattern_match, cross_resource_correlation, etc. Same structure shown
    # as "evidence" in the UI and sent to the AI Reasoning Layer.
    signals: Mapped[dict] = mapped_column(JSON, default=dict)

    classification: Mapped[AnomalyClassification] = str_enum(AnomalyClassification, nullable=False)
    status: Mapped[AnomalyStatus] = str_enum(AnomalyStatus, default=AnomalyStatus.OPEN)

    resource: Mapped["Resource"] = relationship()
    investigation: Mapped["Investigation | None"] = relationship(back_populates="anomaly", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Anomaly {self.resource_id} {self.severity} {self.deviation_pct:.0f}%>"
