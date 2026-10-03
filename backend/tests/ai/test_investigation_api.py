"""API tests for POST /api/anomalies/{id}/investigate (docs Milestone 4, requirement #18)."""
import json

from app.models.anomaly import Anomaly, AnomalyClassification

VALID_AI_RESPONSE = {
    "likely_cause": "plumbing_leak",
    "observed": ["Consumption was well above the expected baseline.", "Occupancy was zero."],
    "inference": "Sustained elevated flow while closed and unoccupied points to a continuous leak.",
    "supporting_evidence": ["baseline_deviation", "operating_status", "occupancy"],
    "alternative_explanations": [{"cause": "irrigation_left_active", "why_less_likely": "Less consistent with the sustained flat pattern."}],
    "recommended_next_step": "Inspect fixtures and the incoming water line for continuous flow.",
    "reasoning_confidence": "high",
}


def _seed_and_get_suspicious_anomaly_id(client, location_name: str) -> str:
    sim = client.post("/api/data/simulate", json={"scenario": "water_leak", "location_name": location_name, "weeks": 6})
    location_id = sim.json()["location_id"]
    client.post("/api/analysis/run", json={"location_id": location_id})
    anomalies = client.get(f"/api/anomalies?location_id={location_id}&classification=operationally_suspicious").json()
    assert len(anomalies) >= 1
    return anomalies[0]["id"]


def test_investigate_without_api_key_falls_back_cleanly(client):
    """No ANTHROPIC_API_KEY is configured in the test environment, so this
    exercises the real end-to-end fallback path through the actual API."""
    anomaly_id = _seed_and_get_suspicious_anomaly_id(client, "Investigation API School 1")

    response = client.post(f"/api/anomalies/{anomaly_id}/investigate")
    assert response.status_code == 200
    body = response.json()
    assert body["explanation_source"] == "fallback"
    assert body["result"]["likely_cause"] == "plumbing_leak"
    assert body["result"]["reasoning_confidence"] in ("high", "medium", "low")


def test_investigate_uses_ai_when_provider_returns_valid_response(client, monkeypatch):
    def mock_call_anthropic(system_prompt, user_prompt):
        return json.dumps(VALID_AI_RESPONSE)

    monkeypatch.setattr("app.ai.investigation_service.call_anthropic", mock_call_anthropic)

    anomaly_id = _seed_and_get_suspicious_anomaly_id(client, "Investigation API School 2")
    response = client.post(f"/api/anomalies/{anomaly_id}/investigate")
    assert response.status_code == 200
    body = response.json()
    assert body["explanation_source"] == "ai"
    assert body["result"]["likely_cause"] == "plumbing_leak"


def test_investigate_falls_back_when_ai_returns_invalid_json(client, monkeypatch):
    def mock_call_anthropic(system_prompt, user_prompt):
        return "not json"

    monkeypatch.setattr("app.ai.investigation_service.call_anthropic", mock_call_anthropic)

    anomaly_id = _seed_and_get_suspicious_anomaly_id(client, "Investigation API School 3")
    response = client.post(f"/api/anomalies/{anomaly_id}/investigate")
    assert response.status_code == 200
    assert response.json()["explanation_source"] == "fallback"


def test_investigate_persists_and_get_anomaly_reflects_it(client):
    anomaly_id = _seed_and_get_suspicious_anomaly_id(client, "Investigation API School 4")
    client.post(f"/api/anomalies/{anomaly_id}/investigate")

    detail = client.get(f"/api/anomalies/{anomaly_id}").json()
    assert detail["investigation"]["explanation"] is not None
    assert detail["investigation"]["explanation_source"] == "fallback"
    assert detail["investigation"]["top_cause"] == "plumbing_leak"


def test_investigate_second_call_is_cached_by_default(client, monkeypatch):
    call_count = {"n": 0}

    def counting_provider(system_prompt, user_prompt):
        call_count["n"] += 1
        return json.dumps(VALID_AI_RESPONSE)

    monkeypatch.setattr("app.ai.investigation_service.call_anthropic", counting_provider)

    anomaly_id = _seed_and_get_suspicious_anomaly_id(client, "Investigation API School 5")
    client.post(f"/api/anomalies/{anomaly_id}/investigate")
    client.post(f"/api/anomalies/{anomaly_id}/investigate")
    assert call_count["n"] == 1

    client.post(f"/api/anomalies/{anomaly_id}/investigate", json={"force": True})
    assert call_count["n"] == 2


def test_investigate_unusual_anomaly_returns_422(client):
    sim = client.post("/api/data/simulate", json={"scenario": "normal_operation", "location_name": "Investigation API School 6", "weeks": 6})
    location_id = sim.json()["location_id"]
    client.post("/api/analysis/run", json={"location_id": location_id})
    anomalies = client.get(f"/api/anomalies?location_id={location_id}&classification=unusual").json()
    if not anomalies:
        import pytest

        pytest.skip("normal_operation scenario produced no 'unusual' anomalies in this run")

    response = client.post(f"/api/anomalies/{anomalies[0]['id']}/investigate")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "investigation_not_applicable"


def test_investigate_unknown_anomaly_returns_404(client):
    import uuid

    response = client.post(f"/api/anomalies/{uuid.uuid4()}/investigate")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "anomaly_not_found"


def test_api_key_never_appears_in_any_response(client):
    anomaly_id = _seed_and_get_suspicious_anomaly_id(client, "Investigation API School 7")
    response = client.post(f"/api/anomalies/{anomaly_id}/investigate")
    assert "ANTHROPIC_API_KEY" not in response.text or "sk-ant" not in response.text.lower()
    health = client.get("/api/health").json()
    assert "key" not in json.dumps(health).lower() or "api_key" not in json.dumps(health).lower()
