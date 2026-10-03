"""End-to-end API tests for the telemetry endpoints (docs Milestone 2, requirement #13)."""
import io


def test_simulate_endpoint_inserts_measurements(client):
    response = client.post(
        "/api/data/simulate",
        json={"scenario": "normal_operation", "location_name": "API Test School", "weeks": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "normal_operation"
    assert body["location_name"] == "API Test School"
    assert body["inserted"]["electricity"] == 7 * 24
    assert body["inserted"]["water"] == 7 * 24


def test_simulate_endpoint_rejects_unknown_scenario(client):
    response = client.post("/api/data/simulate", json={"scenario": "not_a_scenario"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "unknown_scenario"


def test_simulate_is_idempotent_on_second_run(client):
    payload = {"scenario": "normal_operation", "location_name": "API Idempotent School", "weeks": 1}
    first = client.post("/api/data/simulate", json=payload).json()
    second = client.post("/api/data/simulate", json=payload).json()
    assert first["inserted"]["electricity"] == 7 * 24
    # Second run with identical config/seed should skip everything as duplicates.
    assert second["skipped_duplicates"]["electricity"] == 7 * 24
    assert second["inserted"]["electricity"] == 0


def test_measurements_endpoint_returns_paginated_results(client):
    client.post(
        "/api/data/simulate",
        json={"scenario": "normal_operation", "location_name": "API Measurements School", "weeks": 1},
    )
    locations = client.get("/api/locations").json()
    location = next(loc for loc in locations if loc["name"] == "API Measurements School")
    resources = client.get(f"/api/resources?location_id={location['id']}").json()
    electricity_resource = next(r for r in resources if r["resource_type"] == "electricity")

    response = client.get(f"/api/measurements?resource_id={electricity_resource['id']}&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 7 * 24
    assert len(body["items"]) == 10


def test_csv_upload_endpoint_accepts_valid_file(client):
    csv_content = (
        "timestamp,location,resource_type,consumption,occupancy,operating_status\n"
        "2026-07-01T08:00:00Z,CSV API School,electricity,10.0,5,open\n"
        "2026-07-01T09:00:00Z,CSV API School,electricity,11.0,6,open\n"
    )
    response = client.post(
        "/api/data/upload",
        files={"file": ("telemetry.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inserted"] == 2
    assert body["locations_created"] == ["CSV API School"]
    assert body["resources_created"] == 1


def test_csv_upload_endpoint_rejects_invalid_file_with_details(client):
    bad_csv = "timestamp,location,resource_type,consumption\n2026-07-01T08:00:00Z,CSV API School,electricity,-5\n"
    response = client.post(
        "/api/data/upload",
        files={"file": ("bad.csv", io.BytesIO(bad_csv.encode()), "text/csv")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "csv_validation_failed"
    assert len(body["error"]["details"]) >= 1


def test_error_shape_is_consistent_for_404(client):
    import uuid

    response = client.get(f"/api/measurements?resource_id={uuid.uuid4()}")
    # A resource with no data is not an error — should return an empty page, not 404.
    assert response.status_code == 200
    assert response.json()["total"] == 0
