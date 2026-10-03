"""Recommendation — a specific corrective action tied to an Investigation."""
import enum
import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"

    investigation_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("investigations.id"), nullable=False)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[Priority] = str_enum(Priority, default=Priority.MEDIUM)
    estimated_saving: Mapped[float | None] = mapped_column(Float, nullable=True)

    investigation: Mapped["Investigation"] = relationship(back_populates="recommendations")
    interventions: Mapped[list["Intervention"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )

    @property
    def intervention(self) -> "Intervention | None":
        """Convenience accessor — a recommendation has at most one Intervention in practice (docs Milestone 6)."""
        return self.interventions[0] if self.interventions else None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recommendation {self.action_text[:40]!r}>"
