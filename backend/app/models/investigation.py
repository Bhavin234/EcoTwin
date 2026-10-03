"""
Investigation — one per Anomaly. Holds the deterministic candidate-cause
ratings and, if the AI Reasoning Layer produced a validated response, its
structured output. `explanation_source` always records which path actually
produced what's shown to the user (docs/AI_ARCHITECTURE.md,
docs/RELIABILITY_AND_TRUST.md).
"""
import enum
import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class ExplanationSource(str, enum.Enum):
    AI = "ai"
    FALLBACK = "fallback"


class Investigation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigations"

    anomaly_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("anomalies.id"), unique=True, nullable=False)

    # [{"cause": "plumbing_leak", "deterministic_score": "high"}, ...]
    candidate_causes: Mapped[list] = mapped_column(JSON, default=list)

    # Validated structured output — either from the AI Reasoning Layer or
    # the deterministic fallback engine, in the same shape either way:
    # {likely_cause, reasoning, supporting_evidence, alternative_causes,
    #  distinguishing_check, recommended_action}
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation_source: Mapped[ExplanationSource | None] = str_enum(ExplanationSource, nullable=True)

    top_cause: Mapped[str | None] = mapped_column(String(64), nullable=True)

    anomaly: Mapped["Anomaly"] = relationship(back_populates="investigation")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )

    @property
    def recommendation(self) -> "Recommendation | None":
        """
        Convenience accessor: in practice an investigation has at most one
        Recommendation (docs Milestone 5, requirement #3 — recommendations
        are part of the investigation workflow, not a separate product
        area), so API responses expose it singular even though the
        underlying relationship is a list for schema flexibility.
        """
        return self.recommendations[0] if self.recommendations else None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Investigation for anomaly {self.anomaly_id}>"
