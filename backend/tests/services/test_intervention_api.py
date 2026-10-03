"""API tests for the Milestone 5 intervention/impact/demo endpoints."""


def _get_suspicious_anomaly_and_investigate(client, location_name):
    sim = client.post("/api/data/simulate", json={"scenario": "post_intervention_recovery", "location_name": location_name, "weeks": 6})
    location_id = sim.json()["location_id"]
    client.post("/api/analysis/run", json={"location_id": location_id})
    anomalies = client.get(f"/api/anomalies?location_id={location_id}&classification=operationally_suspicious").json()
    anomaly_id = anomalies[0]["id"]
    detail = client.get(f"/api/anomalies/{anomaly_id}").json()
    investigation_id = detail["investigation"]["id"] if detail["investigation"] else None
    if investigation_id is None or detail["investigation"]["explanation"] is None:
        client.post(f"/api/anomalies/{anomaly_id}/investigate")
        detail = client.get(f"/api/anomalies/{anomaly_id}").json()
        investigation_id = detail["investigation"]["id"]
    return anomaly_id, investigation_id, detail["window_end"]


def test_full_intervention_lifecycle_via_api(client):
    anomaly_id, investigation_id, window_end = _get_suspicious_anomaly_and_investigate(client, "Intervention API School 1")

    create_response = client.post(f"/api/investigations/{investigation_id}/interventions")
    assert create_response.status_code == 200
    intervention = create_response.json()
    assert intervention["status"] == "recommended"
    assert intervention["verification_status"] == "pending"

    complete_response = client.post(f"/api/interventions/{intervention['id']}/complete", json={"completed_at": window_end})
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    verify_response = client.post(f"/api/interventions/{intervention['id']}/verify")
    assert verify_response.status_code == 200
    body = verify_response.json()
    assert body["verification_status"] in ("verified", "improvement_detected")
    assert body["avoided_consumption"] > 0


def test_investigation_response_includes_recommendation(client):
    anomaly_id, investigation_id, _ = _get_suspicious_anomaly_and_investigate(client, "Intervention API School 2")
    detail = client.get(f"/api/anomalies/{anomaly_id}").json()
    assert detail["investigation"]["recommendation"] is not None
    assert detail["investigation"]["recommendation"]["action_text"]
    assert detail["investigation"]["recommendation"]["estimated_saving"] > 0
    assert detail["investigation"]["recommendation"]["intervention"] is None


def test_recommendation_reflects_intervention_once_created(client):
    anomaly_id, investigation_id, _ = _get_suspicious_anomaly_and_investigate(client, "Intervention API School 2b")
    client.post(f"/api/investigations/{investigation_id}/interventions")

    detail = client.get(f"/api/anomalies/{anomaly_id}").json()
    assert detail["investigation"]["recommendation"]["intervention"] is not None
    assert detail["investigation"]["recommendation"]["intervention"]["status"] == "recommended"


def test_create_intervention_twice_returns_same_intervention(client):
    _, investigation_id, _ = _get_suspicious_anomaly_and_investigate(client, "Intervention API School 3")
    first = client.post(f"/api/investigations/{investigation_id}/interventions").json()
    second = client.post(f"/api/investigations/{investigation_id}/interventions").json()
    assert first["id"] == second["id"]


def test_verify_before_complete_returns_422(client):
    _, investigation_id, _ = _get_suspicious_anomaly_and_investigate(client, "Intervention API School 4")
    intervention = client.post(f"/api/investigations/{investigation_id}/interventions").json()
    response = client.post(f"/api/interventions/{intervention['id']}/verify")
    assert response.status_code == 422


def test_get_impact_aggregates_across_kinds(client):
    anomaly_id, investigation_id, window_end = _get_suspicious_anomaly_and_investigate(client, "Intervention API School 5")
    intervention = client.post(f"/api/investigations/{investigation_id}/interventions").json()
    client.post(f"/api/interventions/{intervention['id']}/complete", json={"completed_at": window_end})
    client.post(f"/api/interventions/{intervention['id']}/verify")

    response = client.get("/api/impact")
    assert response.status_code == 200
    body = response.json()
    kinds = {s["kind"] for s in body["summary"]}
    assert "estimated" in kinds
    assert len(body["records"]) >= 1


def test_get_impact_filters_by_location(client):
    anomaly_id, investigation_id, window_end = _get_suspicious_anomaly_and_investigate(client, "Intervention API School 6")
    sim_info = client.get(f"/api/anomalies/{anomaly_id}").json()
    location_id = client.get("/api/locations").json()

    response = client.get("/api/impact")
    assert response.status_code == 200


def test_demo_run_endpoint_completes_end_to_end(client):
    response = client.post("/api/demo/run", json={"location_name": "Demo API School"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["likely_cause"] == "plumbing_leak"
    assert body["verification_status"] == "verified"
    assert body["avoided_consumption"] > 0
    # Evidence fields for the frontend's completion screen (docs Milestone 7).
    assert body["resource_type"] == "water"
    assert body["deviation_pct"] is not None
    assert body["persistence_hours"] is not None
    assert body["majority_closed"] is True
    assert body["majority_zero_occupancy"] is True


def test_demo_run_endpoint_is_idempotent(client):
    first = client.post("/api/demo/run", json={"location_name": "Demo API School Idempotent"}).json()
    second = client.post("/api/demo/run", json={"location_name": "Demo API School Idempotent"}).json()
    assert first["anomaly_id"] == second["anomaly_id"]
    assert first["intervention_id"] == second["intervention_id"]


def test_demo_reset_endpoint_clears_and_allows_a_fresh_run(client):
    first = client.post("/api/demo/run", json={"location_name": "Demo API School Reset"}).json()

    reset_response = client.post("/api/demo/reset", json={"location_name": "Demo API School Reset"})
    assert reset_response.status_code == 200
    assert reset_response.json()["reset"] is True

    second = client.post("/api/demo/run", json={"location_name": "Demo API School Reset"}).json()
    assert second["anomaly_id"] != first["anomaly_id"]
    assert second["status"] == "complete"


def test_demo_reset_endpoint_on_unknown_location_reports_false(client):
    response = client.post("/api/demo/reset", json={"location_name": "Never Seeded School"})
    assert response.status_code == 200
    assert response.json()["reset"] is False


def test_get_intervention_not_found_returns_404(client):
    import uuid

    response = client.get(f"/api/interventions/{uuid.uuid4()}")
    assert response.status_code == 404
