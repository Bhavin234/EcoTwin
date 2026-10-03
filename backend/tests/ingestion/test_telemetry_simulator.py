"""
Tests for the baseline telemetry simulator itself: determinism, schema,
record counts, and — per Milestone 2 requirement #14 — that the generated
data actually *behaves* realistically (weekday vs weekend, operating hours
vs closed hours), not just that rows exist.
"""
from datetime import date

import pandas as pd

from app.ingestion.telemetry_simulator import SimulatorConfig, generate_baseline
from app.models.resource import ResourceType


def _config(weeks: int = 3) -> SimulatorConfig:
    return SimulatorConfig(seed=42, start_date=date(2026, 6, 1), weeks=weeks)  # 2026-06-01 is a Monday


def test_generation_is_deterministic():
    config = _config()
    df1 = generate_baseline(config, ResourceType.ELECTRICITY)
    df2 = generate_baseline(config, ResourceType.ELECTRICITY)
    pd.testing.assert_frame_equal(df1, df2)


def test_different_seed_changes_noise():
    df1 = generate_baseline(_config(), ResourceType.ELECTRICITY)
    config2 = _config()
    config2.seed = 999
    df2 = generate_baseline(config2, ResourceType.ELECTRICITY)
    assert not df1["consumption"].equals(df2["consumption"])


def test_generation_is_deterministic_across_separate_processes():
    """
    Regression test for a real bug: the simulator used to derive its
    per-resource noise offset from Python's built-in `hash(str)`, which is
    randomized per-process (PYTHONHASHSEED) unless explicitly disabled.
    That meant the *same* seed and config produced *different* output in
    different process runs — invisible to a same-process determinism test,
    but a real break of the "same seed always reproduces the same dataset"
    guarantee (docs/DEMO.md depends on this for reproducible judging runs).
    This test runs the simulator in two fresh subprocesses and confirms
    identical output.
    """
    import hashlib
    import subprocess
    import sys
    from pathlib import Path

    # The backend's own root directory (parent of the app/ package) —
    # computed dynamically rather than hardcoded, so this test works from
    # any clone location, not just the sandbox this was originally written
    # in (docs Milestone 8, requirement #20: reproducibility / no hidden
    # local file dependencies — this exact hardcoded-path bug was found by
    # that audit).
    backend_root = Path(__file__).resolve().parents[2]

    script = (
        "from datetime import date\n"
        "from app.ingestion.telemetry_simulator import SimulatorConfig, generate_baseline\n"
        "from app.models.resource import ResourceType\n"
        "config = SimulatorConfig(seed=42, start_date=date(2026, 6, 1), weeks=2)\n"
        "df = generate_baseline(config, ResourceType.WATER)\n"
        "print(df['consumption'].round(6).to_csv(index=False))\n"
    )

    outputs = []
    for _ in range(2):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(backend_root),
            capture_output=True,
            text=True,
            check=True,
            env={"PATH": "/usr/bin:/bin"},  # deliberately no PYTHONHASHSEED set, to mirror default behavior
        )
        outputs.append(hashlib.sha256(proc.stdout.encode()).hexdigest())

    assert outputs[0] == outputs[1], "simulator output differs across separate process runs with the same seed"


def test_schema_and_record_count():
    config = _config(weeks=2)
    df = generate_baseline(config, ResourceType.WATER)
    assert list(df.columns) == ["timestamp", "consumption", "occupancy", "operating_status"]
    expected_rows = 2 * 7 * 24  # weeks * days * hourly resolution
    assert len(df) == expected_rows


def test_consumption_is_never_negative():
    df = generate_baseline(_config(), ResourceType.WATER)
    assert (df["consumption"] >= 0).all()


def test_weekday_operating_hours_exceed_weekend_for_electricity():
    """The core realism check: consumption during weekday operating hours
    should clearly exceed weekend consumption at the same hour, because the
    school is closed on weekends."""
    config = _config(weeks=4)
    df = generate_baseline(config, ResourceType.ELECTRICITY)
    df["weekday"] = df["timestamp"].dt.weekday
    df["hour"] = df["timestamp"].dt.hour

    weekday_midday = df[(df["weekday"] < 5) & (df["hour"] == 12)]["consumption"].mean()
    weekend_midday = df[(df["weekday"] >= 5) & (df["hour"] == 12)]["consumption"].mean()

    assert weekday_midday > weekend_midday * 2


def test_operating_hours_exceed_closed_hours_same_weekday():
    config = _config(weeks=4)
    df = generate_baseline(config, ResourceType.WATER)
    df["weekday"] = df["timestamp"].dt.weekday
    df["hour"] = df["timestamp"].dt.hour

    weekday_open = df[(df["weekday"] < 5) & (df["hour"] == 11)]["consumption"].mean()
    weekday_closed = df[(df["weekday"] < 5) & (df["hour"] == 2)]["consumption"].mean()

    assert weekday_open > weekday_closed * 3


def test_occupancy_zero_outside_operating_hours():
    config = _config(weeks=2)
    df = generate_baseline(config, ResourceType.ELECTRICITY)
    df["weekday"] = df["timestamp"].dt.weekday
    df["hour"] = df["timestamp"].dt.hour
    closed_rows = df[(df["weekday"] < 5) & ((df["hour"] < 8) | (df["hour"] >= 18))]
    assert (closed_rows["occupancy"] == 0).all()

    weekend_rows = df[df["weekday"] >= 5]
    assert (weekend_rows["occupancy"] == 0).all()
