"""Synthetic waste-operations data generator.

Produces a small, self-contained dataset that mimics collection operations:
  - data/samples/routes.csv          — route master
  - data/samples/pickups.csv         — daily pickup transactions
  - data/samples/service_events.json — API-style paginated payloads (list of JSON)

All values are generated with a fixed seed; nothing here is real customer or
employer data. Run: python data/generate_synthetic_data.py [--rows N]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
DATA_DIR = Path(__file__).resolve().parent / "samples"

TRUCKS = ["TK-101", "TK-102", "TK-103", "TK-104"]
DRIVERS = ["A. Nguyen", "M. Patel", "J. Garcia", "R. Kim", "S. Okafor"]
ZONES = ["North", "South", "East", "West", "Central"]
EVENT_TYPES = ["MISSED_PICKUP", "CONTAINER_DAMAGE", "OVERFLOW", "RESCHEDULE", "NONE"]
PRIORITIES = ["LOW", "MEDIUM", "HIGH"]


def _rng(seed: int = SEED) -> random.Random:
    return random.Random(seed)


def generate_routes(rng: random.Random, n: int = 40) -> list[dict]:
    routes = []
    for i in range(1, n + 1):
        routes.append(
            {
                "route_id": f"R-{i:03d}",
                "zone": rng.choice(ZONES),
                "truck_id": rng.choice(TRUCKS),
                "driver_name": rng.choice(DRIVERS),
                "stops_planned": rng.randint(60, 180),
            }
        )
    return routes


def generate_pickups(rng: random.Random, routes: list[dict], days: int = 14) -> list[dict]:
    pickups: list[dict] = []
    pickup_id = 1
    start = date(2026, 9, 20)
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        for route in routes:
            # 0–4 pickups per route per day keeps the file small
            for _ in range(rng.randint(0, 4)):
                tonnage = round(rng.uniform(0.2, 4.5), 2)
                pickups.append(
                    {
                        "pickup_id": f"P-{pickup_id:06d}",
                        "route_id": route["route_id"],
                        "pickup_date": day.isoformat(),
                        "tonnage": tonnage,
                        "material": rng.choice(["MSW", "RECYCLE", "ORGANICS"]),
                    }
                )
                pickup_id += 1
    return pickups


def generate_service_events(rng: random.Random, routes: list[dict], days: int = 14) -> list[dict]:
    events: list[dict] = []
    event_id = 1
    start = date(2026, 9, 20)
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        for _ in range(rng.randint(2, 6)):
            route = rng.choice(routes)
            events.append(
                {
                    "event_id": f"E-{event_id:06d}",
                    "route_id": route["route_id"],
                    "event_date": day.isoformat(),
                    "event_type": rng.choice(EVENT_TYPES),
                    "priority": rng.choice(PRIORITIES),
                }
            )
            event_id += 1
    return events


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--routes", type=int, default=40, help="number of routes to generate")
    parser.add_argument("--days", type=int, default=14, help="days of pickup history")
    args = parser.parse_args()

    rng = _rng(args.seed)
    routes = generate_routes(rng, n=args.routes)
    pickups = generate_pickups(rng, routes, days=args.days)
    events = generate_service_events(rng, routes, days=args.days)

    _write_csv(DATA_DIR / "routes.csv", routes)
    _write_csv(DATA_DIR / "pickups.csv", pickups)
    (DATA_DIR / "service_events.json").write_text(json.dumps(events, indent=2))
    print(
        f"Wrote {len(routes)} routes, {len(pickups)} pickups, "
        f"{len(events)} service events to {DATA_DIR}"
    )


if __name__ == "__main__":
    main()
