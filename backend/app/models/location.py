"""Location — a physical site EcoTwin monitors (see docs/DATA_MODEL.md)."""
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")

    # e.g. {"mon": ["08:00", "18:00"], "sat": null, "sun": null}
    # Drives the `operating_status` context signal used by the anomaly
    # engine (docs/ANOMALY_DETECTION.md).
    operating_hours: Mapped[dict] = mapped_column(JSON, default=dict)

    resources: Mapped[list["Resource"]] = relationship(back_populates="location", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Location {self.name}>"
