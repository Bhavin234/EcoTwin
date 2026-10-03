"""
EcoTwin CLI.

Usage:
    python -m app.cli seed-demo [--scenario NAME] [--reset]
    python -m app.cli list-scenarios
    python -m app.cli investigate-demo [--scenario NAME]

`seed-demo` defaults to the "post_intervention_recovery" scenario, which is
the full timeline used in the judging demo (docs/DEMO.md): weeks of normal
baseline, an after-hours water-leak anomaly in the final week, followed by
a recovery window. Running it twice with the same config is a no-op the
second time (duplicate measurements are skipped, not re-inserted) unless
`--reset` is passed, which clears existing telemetry first.

`investigate-demo` (Milestone 4) seeds the demo dataset if needed, runs the
deterministic analytics engine, finds the highest-severity
operationally_suspicious anomaly, and investigates it — using the real
Anthropic API if `ANTHROPIC_API_KEY` is configured, or the deterministic
fallback engine (clearly labeled as such) if not. This never fails the
whole command just because no API key is present (docs Milestone 4,
requirement #22).
"""
from __future__ import annotations

import argparse
import sys

from app.core.database import Base, SessionLocal, engine, init_db
from app.ingestion.scenarios import SCENARIO_NAMES
from app.services.scenario_runner import run_scenario


def _reset_telemetry() -> None:
    """Drop and recreate every table — a clean slate for reseeding.

    This is a development convenience for regenerating the demo dataset; it
    is not exposed over the API (docs Milestone 2 requirement #11: "It
    should be possible to reset and regenerate the demo data without
    manually modifying database records" — this is that mechanism).
    """
    from app import models  # noqa: F401  (register models before drop/create)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def cmd_seed_demo(scenario: str, reset: bool, location_name: str, seed: int | None, weeks: int | None) -> None:
    if reset:
        print("Resetting database...")
        _reset_telemetry()
    else:
        init_db()

    db = SessionLocal()
    try:
        result = run_scenario(db, scenario, location_name=location_name, seed=seed, weeks=weeks)
    finally:
        db.close()

    print(f"Scenario '{result.scenario}' seeded for location '{result.location_name}' ({result.location_id}).")
    print(f"Period: {result.period_start} to {result.period_end}")
    for resource_type, count in result.inserted.items():
        skipped = result.skipped_duplicates.get(resource_type, 0)
        print(f"  {resource_type}: inserted {count}, skipped {skipped} duplicate(s)")


def cmd_list_scenarios() -> None:
    print("Available scenarios:")
    for name in SCENARIO_NAMES:
        print(f"  - {name}")


def cmd_investigate_demo(scenario: str, location_name: str) -> None:
    from app.core.config import get_settings
    from app.models.anomaly import Anomaly, AnomalyClassification
    from app.models.location import Location
    from app.services.analytics_service import run_analysis_for_location

    settings = get_settings()
    print(f"AI Reasoning Layer: {'enabled (ANTHROPIC_API_KEY is set)' if settings.ai_enabled else 'disabled — deterministic fallback will be used'}")

    init_db()
    db = SessionLocal()
    try:
        location = db.query(Location).filter(Location.name == location_name).first()
        if location is None:
            print(f"No existing data for '{location_name}', seeding scenario '{scenario}'...")
            run_scenario(db, scenario, location_name=location_name)
            location = db.query(Location).filter(Location.name == location_name).first()

        print("Running deterministic analytics engine...")
        run_analysis_for_location(db, location.id)

        suspicious = (
            db.query(Anomaly)
            .join(Anomaly.resource)
            .filter(Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
            .all()
        )
        if not suspicious:
            print("No operationally_suspicious anomalies found — nothing to investigate.")
            return

        severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        suspicious.sort(key=lambda a: severity_rank.get(a.severity.value, -1), reverse=True)
        anomaly = suspicious[0]
        print(f"\nInvestigating anomaly {anomaly.id} ({anomaly.severity.value}, {anomaly.window_start} -> {anomaly.window_end})...")

        from app.ai.investigation_service import investigate_anomaly

        outcome = investigate_anomaly(db, anomaly.id, force=True)

        print(f"\nExplanation source: {outcome.source.upper()}")
        if outcome.fallback_reason:
            print(f"(AI unavailable — deterministic fallback used. Reason: {outcome.fallback_reason})")
        print(f"\nLikely cause: {outcome.result.likely_cause}")
        print(f"Reasoning confidence: {outcome.result.reasoning_confidence}")
        print(f"\nObserved:")
        for item in outcome.result.observed:
            print(f"  - {item}")
        print(f"\nInference:\n  {outcome.result.inference}")
        print(f"\nAlternative explanations:")
        for alt in outcome.result.alternative_explanations:
            print(f"  - {alt.cause}: {alt.why_less_likely}")
        print(f"\nRecommended next step:\n  {outcome.result.recommended_next_step}")
    finally:
        db.close()


def cmd_run_demo(scenario: str, location_name: str) -> None:
    from app.services.demo_service import run_demo

    init_db()
    db = SessionLocal()
    try:
        result = run_demo(db, scenario=scenario, location_name=location_name)
    finally:
        db.close()

    if result.status == "no_anomaly_found":
        print(result.message)
        return

    print(f"Location: {result.location_name} ({result.location_id})")
    print(f"Anomaly: {result.severity} severity, id={result.anomaly_id}")
    print(f"Investigation: {result.likely_cause} (source: {result.explanation_source})")
    print(f"Recommendation: {result.recommendation_text}")
    print(f"Intervention: {result.intervention_id}")
    print(f"\nVerification status: {result.verification_status.upper()}")
    print(f"  {result.message}")
    if result.avoided_consumption is not None:
        print(f"\nAvoided consumption: {result.avoided_consumption:.2f}")
        print(f"Money saved: {result.money_saved:.2f}")
        print(f"CO2e avoided: {result.co2e_avoided_kg:.3f} kg")


def cmd_reset_demo(location_name: str) -> None:
    from app.services.demo_service import reset_demo_location

    init_db()
    db = SessionLocal()
    try:
        was_reset = reset_demo_location(db, location_name=location_name)
    finally:
        db.close()
    print(f"Reset '{location_name}': {'done' if was_reset else 'nothing to reset (location not found)'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="EcoTwin developer CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_parser = subparsers.add_parser("seed-demo", help="Generate and insert a demo telemetry dataset.")
    seed_parser.add_argument(
        "--scenario", default="post_intervention_recovery", choices=SCENARIO_NAMES, help="Scenario to seed."
    )
    seed_parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding.")
    seed_parser.add_argument("--location-name", default="Greenfield Public School")
    seed_parser.add_argument("--seed", type=int, default=None, help="Override the deterministic random seed.")
    seed_parser.add_argument("--weeks", type=int, default=None, help="Override the number of weeks generated.")

    subparsers.add_parser("list-scenarios", help="List the available named scenarios.")

    investigate_parser = subparsers.add_parser(
        "investigate-demo", help="Seed demo data if needed, run analytics, and investigate the top anomaly."
    )
    investigate_parser.add_argument(
        "--scenario", default="post_intervention_recovery", choices=SCENARIO_NAMES,
    )
    investigate_parser.add_argument("--location-name", default="Greenfield Public School")

    demo_parser = subparsers.add_parser(
        "run-demo", help="Run the complete backend demo workflow: seed -> analyze -> investigate -> recommend -> intervene -> verify."
    )
    demo_parser.add_argument("--scenario", default="post_intervention_recovery", choices=SCENARIO_NAMES)
    demo_parser.add_argument("--location-name", default="Greenfield Public School")

    reset_demo_parser = subparsers.add_parser(
        "reset-demo", help="Fully clear one demo location's data (scoped — never touches other locations)."
    )
    reset_demo_parser.add_argument("--location-name", default="Greenfield Public School")

    args = parser.parse_args(argv)

    if args.command == "seed-demo":
        cmd_seed_demo(args.scenario, args.reset, args.location_name, args.seed, args.weeks)
    elif args.command == "list-scenarios":
        cmd_list_scenarios()
    elif args.command == "investigate-demo":
        cmd_investigate_demo(args.scenario, args.location_name)
    elif args.command == "run-demo":
        cmd_run_demo(args.scenario, args.location_name)
    elif args.command == "reset-demo":
        cmd_reset_demo(args.location_name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
