"""
Measurement — a single telemetry reading for a Resource.

The `source` field records where a row came from (csv upload, the
deterministic demo simulator, or a future API push standing in for a real
smart meter / BMS feed) but every downstream engine treats all sources
identically — this is what makes ingestion hardware-agnostic
(docs/ARCHITECTURE.md, "Telemetry Ingestion Layer").
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, str_enum


class MeasurementSource(str, enum.Enum):
    CSV = "csv"
    SIMULATOR = "simulator"
    API = "api"


class OperatingStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (Index("ix_measurements_resource_timestamp", "resource_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("resources.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumption: Mapped[float] = mapped_column(Float, nullable=False)
    occupancy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operating_status: Mapped[OperatingStatus] = str_enum(OperatingStatus, default=OperatingStatus.UNKNOWN)
    source: Mapped[MeasurementSource] = str_enum(MeasurementSource, nullable=False)

    # Which named simulator scenario produced this row (e.g. "water_leak"),
    # null for CSV/API rows. Purely descriptive metadata for later analysis
    # and test assertions — it is NOT an anomaly flag. The simulator never
    # writes a ground-truth "this is an anomaly" verdict; the future
    # Anomaly Engine (Milestone 3) must discover anomalies from the
    # measurement values and context alone (docs/ROADMAP.md, Milestone 2
    # requirement "do not hardcode the final anomaly").
    scenario: Mapped[str | None] = mapped_column(String(64), nullable=True)

    resource: Mapped["Resource"] = relationship(back_populates="measurements")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Measurement {self.resource_id} {self.timestamp} = {self.consumption}>"
