"""
Baseline — cached rolling mean/stddev for a (resource, hour_of_day,
day_of_week) slot, computed by the Baseline Engine (Milestone 3). Stored
rather than recomputed on every request because the anomaly and
verification engines both need fast lookups against it.

`sample_count` drives the cold-start gate documented in
docs/ANOMALY_DETECTION.md: slots with too few comparable historical points
are never used to raise an anomaly.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import GUID, utcnow


class Baseline(Base):
    __tablename__ = "baselines"
    __table_args__ = (
        UniqueConstraint("resource_id", "hour_of_day", "day_of_week", name="uq_baseline_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("resources.id"), nullable=False)
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-23
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    mean: Mapped[float] = mapped_column(Float, nullable=False)
    stddev: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
