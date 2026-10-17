"""Bronze load orchestrator — the entry point for the nightly ingestion run.

Flow:
  1. Load route + pickup CSVs from the file drop (data/samples/) into data/bronze/
  2. Ingest service events from the REST API into data/bronze/service_events.jsonl
     (offline demo: falls back to the sample JSON payload shipped in the repo)
  3. Write a run manifest so every bronze file is traceable to a run timestamp.

Usage: python ingestion/run_bronze_load.py [--offline]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from api_client import APIClientError, APIConfig, PaginatedAPIClient
from csv_loader import load_to_bronze

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
BRONZE = ROOT / "data" / "bronze"


def load_api_events(offline: bool) -> int:
    """Return count of service-event records landed in bronze."""
    target = BRONZE / "service_events.jsonl"
    if offline:
        records = json.loads((SAMPLES / "service_events.json").read_text())
        with target.open("w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")
        return len(records)
    client = PaginatedAPIClient(APIConfig.from_env())
    return client.fetch_to_jsonl(target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true",
                        help="use shipped sample payloads instead of the live API")
    args = parser.parse_args()

    manifest: dict[str, object] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "offline": args.offline,
        "sources": {},
    }
    sources = manifest["sources"]  # type: ignore[assignment]
    assert isinstance(sources, dict)

    for source in ("routes", "pickups"):
        result = load_to_bronze(source, SAMPLES / f"{source}.csv", BRONZE)
        sources[source] = {"rows": result.rows, "status": "ok"}

    try:
        n_events = load_api_events(offline=args.offline)
        sources["service_events"] = {"rows": n_events, "status": "ok"}
    except APIClientError as exc:
        sources["service_events"] = {"rows": 0, "status": f"failed: {exc}"}
        raise SystemExit(f"Bronze load failed on service events: {exc}")

    (BRONZE / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
