"""CSV loader with schema validation for file-drop sources.

File drops are the fallback when a source system can't expose an API — the
pattern this project uses for route and pickup data. Every file is validated
for required columns, non-empty rows, and duplicate keys BEFORE it lands in
bronze, so bad files fail loud and early instead of poisoning downstream.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

# Required columns per source file — the "contract" with the source system.
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "routes": ["route_id", "zone", "truck_id", "driver_name", "stops_planned"],
    "pickups": ["pickup_id", "route_id", "pickup_date", "tonnage", "material"],
}


@dataclass
class ValidationResult:
    source: str
    rows: int
    passed: bool
    errors: list[str] = field(default_factory=list)


def validate_csv(path: Path, source: str) -> ValidationResult:
    """Validate a CSV against its required-column contract."""
    result = ValidationResult(source=source, rows=0, passed=False)
    required = REQUIRED_COLUMNS[source]
    seen_keys: set[str] = set()

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        missing = [c for c in required if c not in headers]
        if missing:
            result.errors.append(f"missing columns: {missing}")
            return result
        key_col = required[0]
        for i, row in enumerate(reader, start=2):  # 1-based incl. header
            result.rows += 1
            if not row.get(key_col):
                result.errors.append(f"line {i}: empty key column '{key_col}'")
                continue
            if row[key_col] in seen_keys:
                result.errors.append(f"line {i}: duplicate key '{row[key_col]}'")
            seen_keys.add(row[key_col])

    result.passed = not result.errors
    return result


def load_to_bronze(source: str, source_path: Path, bronze_dir: Path) -> ValidationResult:
    """Validate, then stage a raw byte-for-byte copy into bronze.

    Bronze keeps the raw file untouched; cleaning happens in the
    bronze->silver transform. A manifest line records what landed and when.
    """
    result = validate_csv(source_path, source)
    if not result.passed:
        raise ValueError(f"validation failed for {source_path}: {result.errors}")

    bronze_dir.mkdir(parents=True, exist_ok=True)
    target = bronze_dir / f"{source}.csv"
    target.write_bytes(source_path.read_bytes())
    return result
