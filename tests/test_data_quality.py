"""Data-quality tests: the same rules the bronze->silver SQL enforces.

These run in CI on the synthetic sample data, so a schema drift in the source
files fails the build before anything is loaded.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingestion"))

import generate_synthetic_data
from csv_loader import validate_csv

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def test_csv_contracts_validate(tmp_path):
    # Use the generator directly for deterministic output
    rng = generate_synthetic_data._rng()
    routes = generate_synthetic_data.generate_routes(rng, n=10)
    pickups = generate_synthetic_data.generate_pickups(rng, routes, days=3)
    generate_synthetic_data._write_csv(tmp_path / "routes.csv", routes)
    generate_synthetic_data._write_csv(tmp_path / "pickups.csv", pickups)

    for source in ("routes", "pickups"):
        result = validate_csv(tmp_path / f"{source}.csv", source)
        assert result.passed, f"{source}: {result.errors}"


def test_csv_validation_rejects_missing_columns(tmp_path):
    bad = tmp_path / "pickups.csv"
    bad.write_text("pickup_id,route_id\nP-1,R-001\n")
    result = validate_csv(bad, "pickups")
    assert not result.passed
    assert any("missing columns" in e for e in result.errors)


def test_csv_validation_rejects_duplicate_keys(tmp_path):
    bad = tmp_path / "routes.csv"
    bad.write_text(
        "route_id,zone,truck_id,driver_name,stops_planned\n"
        "R-001,North,TK-101,A. Nguyen,100\n"
        "R-001,South,TK-102,M. Patel,120\n"
    )
    result = validate_csv(bad, "routes")
    assert not result.passed
    assert any("duplicate key" in e for e in result.errors)


def test_pickups_have_no_negative_tonnage():
    rows = _read_csv(SAMPLES / "pickups.csv")
    bad = [r for r in rows if float(r["tonnage"]) < 0]
    assert not bad, f"{len(bad)} rows with negative tonnage"


def test_service_events_reference_known_routes():
    routes = {r["route_id"] for r in _read_csv(SAMPLES / "routes.csv")}
    events = json.loads((SAMPLES / "service_events.json").read_text())
    unknown = [e for e in events if e["route_id"] not in routes]
    assert not unknown, f"{len(unknown)} events reference unknown routes"
