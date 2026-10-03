"""
Intervention — records that a user marked a recommendation complete, and
tracks its (separate) verification outcome.

Revised in Milestone 5: `status` is now a simple action lifecycle
(`recommended` -> `in_progress` -> `completed`), and `verification_status`
is a distinct, richer set of deterministic states describing whether the
post-intervention telemetry actually demonstrates improvement. These are
deliberately different concepts (docs/ANOMALY_DETECTION.md /
Milestone 5, requirement #11): completing an intervention means "the
action was reported as performed"; verification means "the telemetry
demonstrates consumption improved." The original Milestone 1 draft
conflated them into one `status` enum (`pending_verification` /
`verified_success` / `verified_no_change`) before the verification
workflow existed to justify the distinction — see `DATA_MODEL.md` for the
full rationale.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class InterventionStatus(str, enum.Enum):
    """Action lifecycle — has the recommended action been carried out?"""

    RECOMMENDED = "recommended"  # created, not yet acted on
    IN_PROGRESS = "in_progress"  # optionally used if a team wants to track "someone is on it"
    COMPLETED = "completed"  # reported as done — NOT the same as verified


class VerificationStatus(str, enum.Enum):
    """Deterministic verification outcome — does the telemetry demonstrate improvement?"""

    PENDING = "pending"  # not yet evaluated (e.g. intervention not completed yet)
    INSUFFICIENT_DATA = "insufficient_data"  # not enough post-intervention telemetry yet to judge
    NO_MEASURABLE_IMPROVEMENT = "no_measurable_improvement"  # post-intervention consumption is still elevated
    IMPROVEMENT_DETECTED = "improvement_detected"  # consumption dropped and looks roughly normal again, but with lower-confidence context (e.g. a "limited" rather than "sufficient" baseline)
    VERIFIED = "verified"  # consumption is back within the normal range, backed by a "sufficient"-confidence baseline


class Intervention(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interventions"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("recommendations.id"), nullable=False)
    marked_complete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[InterventionStatus] = str_enum(InterventionStatus, default=InterventionStatus.RECOMMENDED)
    verification_status: Mapped[VerificationStatus] = str_enum(VerificationStatus, default=VerificationStatus.PENDING)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="interventions")
    impact_records: Mapped[list["ImpactRecord"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Intervention {self.status} / verification={self.verification_status}>"
