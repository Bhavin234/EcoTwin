"""
SQLAlchemy ORM models for EcoTwin.

Schema follows docs/DATA_MODEL.md exactly. Importing this package registers
every model on `Base.metadata`, which is what `init_db()` relies on.
"""
from app.models.location import Location
from app.models.resource import Resource
from app.models.measurement import Measurement
from app.models.baseline import Baseline
from app.models.anomaly import Anomaly
from app.models.investigation import Investigation
from app.models.recommendation import Recommendation
from app.models.intervention import Intervention
from app.models.impact import ImpactRecord
from app.models.factors import CostFactor, EmissionFactor

__all__ = [
    "Location",
    "Resource",
    "Measurement",
    "Baseline",
    "Anomaly",
    "Investigation",
    "Recommendation",
    "Intervention",
    "ImpactRecord",
    "CostFactor",
    "EmissionFactor",
]
