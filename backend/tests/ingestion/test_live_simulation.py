from app.ingestion.scenarios import scenario_normal_operation
from app.models.measurement import MeasurementSource
from app.models.resource import Resource
from app.services.live_simulation_service import advance_live_stream
from app.services.scenario_runner import run_scenario


def test_live_stream_appends_new_deterministic_readings(db_session):
    seeded = run_scenario(db_session, "normal_operation", location_name="Live Test Site", weeks=1)
    result = advance_live_stream(db_session, location_id=seeded.location_id, hours=2, seed=42)

    assert result.inserted == 4
    assert result.simulated_end > result.simulated_start

    resources = db_session.query(Resource).filter(Resource.location_id == seeded.location_id).all()
    for resource in resources:
        latest = sorted(resource.measurements, key=lambda m: m.timestamp)[-2:]
        assert len(latest) == 2
        assert all(m.source == MeasurementSource.SIMULATOR for m in latest)
        assert all(m.scenario == "live_stream" for m in latest)


def test_live_stream_rejects_invalid_hour_window(db_session):
    seeded = run_scenario(db_session, "normal_operation", location_name="Live Invalid Hours", weeks=1)
    try:
        advance_live_stream(db_session, location_id=seeded.location_id, hours=25)
    except ValueError as exc:
        assert "between 1 and 24" in str(exc)
    else:
        raise AssertionError("Expected invalid live simulation window to be rejected")
