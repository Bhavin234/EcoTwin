"""
Database integrity tests (docs Milestone 8, requirements #12-13).
"""
from app.models.anomaly import Anomaly
from app.models.impact import ImpactRecord
from app.models.intervention import Intervention
from app.models.investigation import Investigation
from app.models.location import Location
from app.models.measurement import Measurement
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.services.demo_service import reset_demo_location, run_demo


def test_repeated_demo_runs_then_reset_then_rerun_leaves_clean_state(db_session):
    location_name = "Hardening DB Integrity School"

    run_demo(db_session, location_name=location_name)
    run_demo(db_session, location_name=location_name)
    run_demo(db_session, location_name=location_name)

    location = db_session.query(Location).filter(Location.name == location_name).first()
    resource_ids = [r.id for r in db_session.query(Resource).filter(Resource.location_id == location.id).all()]

    anomalies = db_session.query(Anomaly).filter(Anomaly.resource_id.in_(resource_ids)).all()
    interventions = db_session.query(Intervention).join(Recommendation).join(Investigation).filter(
        Investigation.anomaly_id.in_([a.id for a in anomalies])
    ).all()
    impact_records = db_session.query(ImpactRecord).filter(ImpactRecord.resource_id.in_(resource_ids)).all()

    # Three repeated runs must not have produced three sets of interventions/impact records.
    assert len(interventions) == 1
    assert len(impact_records) <= 2  # one estimated + one verified, not accumulating

    reset_demo_location(db_session, location_name=location_name)
    assert db_session.query(Location).filter(Location.name == location_name).first() is None
    assert db_session.query(Resource).filter(Resource.id.in_(resource_ids)).count() == 0
    assert db_session.query(Measurement).filter(Measurement.resource_id.in_(resource_ids)).count() == 0
    assert db_session.query(Anomaly).filter(Anomaly.resource_id.in_(resource_ids)).count() == 0

    fresh = run_demo(db_session, location_name=location_name)
    assert fresh.status == "complete"


def test_reset_does_not_touch_other_locations_data_or_relationships(db_session):
    run_demo(db_session, location_name="Hardening DB Integrity School Keep")
    run_demo(db_session, location_name="Hardening DB Integrity School Delete")

    keep_location = db_session.query(Location).filter(Location.name == "Hardening DB Integrity School Keep").first()
    keep_resource_ids = [r.id for r in db_session.query(Resource).filter(Resource.location_id == keep_location.id).all()]
    keep_measurement_count_before = db_session.query(Measurement).filter(Measurement.resource_id.in_(keep_resource_ids)).count()
    keep_anomaly_count_before = db_session.query(Anomaly).filter(Anomaly.resource_id.in_(keep_resource_ids)).count()

    reset_demo_location(db_session, location_name="Hardening DB Integrity School Delete")

    # The untouched location's data must be completely unaffected.
    assert db_session.query(Location).filter(Location.name == "Hardening DB Integrity School Keep").first() is not None
    keep_measurement_count_after = db_session.query(Measurement).filter(Measurement.resource_id.in_(keep_resource_ids)).count()
    keep_anomaly_count_after = db_session.query(Anomaly).filter(Anomaly.resource_id.in_(keep_resource_ids)).count()
    assert keep_measurement_count_after == keep_measurement_count_before
    assert keep_anomaly_count_after == keep_anomaly_count_before


def test_no_orphaned_investigations_recommendations_interventions_after_reset(db_session):
    location_name = "Hardening DB Integrity School Orphans"
    run_demo(db_session, location_name=location_name)
    reset_demo_location(db_session, location_name=location_name)

    # Every Investigation must still point at a real Anomaly; every
    # Recommendation at a real Investigation; every Intervention at a real
    # Recommendation — globally, not just for the reset location — since a
    # buggy scoped delete could otherwise leave dangling rows anywhere.
    all_investigation_anomaly_ids = {i.anomaly_id for i in db_session.query(Investigation).all()}
    all_anomaly_ids = {a.id for a in db_session.query(Anomaly).all()}
    assert all_investigation_anomaly_ids.issubset(all_anomaly_ids)

    all_recommendation_investigation_ids = {r.investigation_id for r in db_session.query(Recommendation).all()}
    all_investigation_ids = {i.id for i in db_session.query(Investigation).all()}
    assert all_recommendation_investigation_ids.issubset(all_investigation_ids)

    all_intervention_recommendation_ids = {iv.recommendation_id for iv in db_session.query(Intervention).all()}
    all_recommendation_ids = {r.id for r in db_session.query(Recommendation).all()}
    assert all_intervention_recommendation_ids.issubset(all_recommendation_ids)


def test_impact_records_reference_valid_resources(db_session):
    run_demo(db_session, location_name="Hardening DB Integrity School ImpactRefs")
    all_resource_ids = {r.id for r in db_session.query(Resource).all()}
    for record in db_session.query(ImpactRecord).all():
        if record.resource_id is not None:
            assert record.resource_id in all_resource_ids
