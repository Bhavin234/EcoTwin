"""Milestone 1 tests: the app boots, connects to its database, and the
health endpoint reports accurately (docs/ROADMAP.md, Milestone 1)."""


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "EcoTwin" in response.json()["message"]


def test_health_endpoint_reports_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    # No ANTHROPIC_API_KEY is set in the test environment, so the app must
    # report the AI layer as disabled and still function (fallback path).
    assert body["ai_reasoning_layer"].startswith("disabled")


def test_models_create_tables_without_error():
    """Importing app.models and calling init_db() should not raise, and
    every table from docs/DATA_MODEL.md should exist afterwards."""
    from sqlalchemy import inspect

    from app.core.database import engine

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    expected = {
        "locations",
        "resources",
        "measurements",
        "baselines",
        "anomalies",
        "investigations",
        "recommendations",
        "interventions",
        "impact_records",
        "cost_factors",
        "emission_factors",
    }
    assert expected.issubset(table_names)
