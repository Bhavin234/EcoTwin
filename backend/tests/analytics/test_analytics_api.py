"""API-level tests for the analytics endpoints (docs Milestone 3, requirement #17)."""


def test_run_analysis_persists_and_returns_summary(client):
    sim = client.post(
        "/api/data/simulate",
        json={"scenario": "water_leak", "location_name": "Analytics API School", "weeks": 6},
    )
    location_id = sim.json()["location_id"]

    response = client.post("/api/analysis/run", json={"location_id": location_id})
    assert response.status_code == 200
    body = response.json()
    assert body["location_name"] == "Analytics API School"
    resource_summaries = {r["resource_type"]: r for r in body["resources"]}
    assert "water" in resource_summaries
    assert resource_summaries["water"]["total_anomalies"] >= 1
    assert resource_summaries["water"]["operationally_suspicious"] >= 1


def test_run_analysis_unknown_location_returns_404(client):
    import uuid

    response = client.post("/api/analysis/run", json={"location_id": str(uuid.uuid4())})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "location_not_found"


def test_list_and_get_anomalies(client):
    sim = client.post(
        "/api/data/simulate",
        json={"scenario": "electricity_overconsumption", "location_name": "Analytics API School 2", "weeks": 6},
    )
    location_id = sim.json()["location_id"]
    client.post("/api/analysis/run", json={"location_id": location_id})

    list_response = client.get(f"/api/anomalies?location_id={location_id}")
    assert list_response.status_code == 200
    anomalies = list_response.json()
    assert len(anomalies) >= 1

    detail_response = client.get(f"/api/anomalies/{anomalies[0]['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert "signals" in detail
    assert isinstance(detail["signals"], dict)
    assert isinstance(detail["evidence"], list)
    assert len(detail["evidence"]) >= 1
    assert all({"signal", "description"}.issubset(e.keys()) for e in detail["evidence"])


def test_operationally_suspicious_anomaly_has_investigation_with_candidate_causes(client):
    sim = client.post(
        "/api/data/simulate",
        json={"scenario": "water_leak", "location_name": "Analytics API School 3", "weeks": 6},
    )
    location_id = sim.json()["location_id"]
    client.post("/api/analysis/run", json={"location_id": location_id})

    anomalies = client.get(
        f"/api/anomalies?location_id={location_id}&classification=operationally_suspicious"
    ).json()
    assert len(anomalies) >= 1

    detail = client.get(f"/api/anomalies/{anomalies[0]['id']}").json()
    assert detail["investigation"] is not None
    assert len(detail["investigation"]["candidate_causes"]) >= 1
    assert detail["investigation"]["explanation"] is None  # Milestone 4 fills this in
    assert detail["investigation"]["explanation_source"] is None


def test_anomaly_not_found_returns_404(client):
    import uuid

    response = client.get(f"/api/anomalies/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "anomaly_not_found"


def test_get_factors_seeds_and_returns_defaults(client):
    response = client.get("/api/config/factors")
    assert response.status_code == 200
    body = response.json()
    assert len(body["cost_factors"]) >= 2
    assert len(body["emission_factors"]) >= 2
    resource_types = {f["resource_type"] for f in body["cost_factors"]}
    assert {"electricity", "water"}.issubset(resource_types)


def test_update_cost_factor(client):
    factors = client.get("/api/config/factors").json()
    cost_factor = next(f for f in factors["cost_factors"] if f["resource_type"] == "electricity")

    response = client.put(f"/api/config/factors/cost/{cost_factor['id']}", json={"rate": 9.5})
    assert response.status_code == 200
    assert response.json()["rate"] == 9.5


def test_update_emission_factor(client):
    factors = client.get("/api/config/factors").json()
    emission_factor = next(f for f in factors["emission_factors"] if f["resource_type"] == "water")

    response = client.put(
        f"/api/config/factors/emission/{emission_factor['id']}",
        json={"factor_value": 0.0004, "source": "Updated citation"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["factor_value"] == 0.0004
    assert body["source"] == "Updated citation"


def test_get_resource_baselines(client):
    sim = client.post("/api/data/simulate", json={"scenario": "normal_operation", "location_name": "Baseline API School", "weeks": 6})
    location_id = sim.json()["location_id"]
    client.post("/api/analysis/run", json={"location_id": location_id})
    resources = client.get(f"/api/resources?location_id={location_id}").json()
    resource_id = resources[0]["id"]

    response = client.get(f"/api/resources/{resource_id}/baselines")
    assert response.status_code == 200
    baselines = response.json()
    assert len(baselines) > 0
    assert set(baselines[0].keys()) == {"hour_of_day", "day_of_week", "mean", "stddev", "sample_count"}
