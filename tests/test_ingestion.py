"""Tests for the API ingestion client.

A local in-process HTTP server plays the role of the source REST API, so
pagination and retry behavior are tested without any external dependency.
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingestion"))

from api_client import APIClientError, APIConfig, PaginatedAPIClient

RECORDS = [{"id": i, "route_id": f"R-{i % 5:03d}"} for i in range(1, 6)]
_CALLS: list[str] = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence noisy test server
        pass

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        page = int(query.get("page", ["1"])[0])
        page_size = int(query.get("page_size", ["100"])[0])
        _CALLS.append(self.path)

        # First request to page 1 simulates a transient 503 (retry test).
        if page == 1 and len(_CALLS) == 1:
            self.send_response(503)
            self.end_headers()
            return

        start = (page - 1) * page_size
        chunk = RECORDS[start : start + page_size]
        body = json.dumps({"records": chunk}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def _client(**overrides):
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cfg = APIConfig(base_url=f"http://127.0.0.1:{server.server_port}/v1/events",
                    page_size=2, **overrides)
    return server, PaginatedAPIClient(cfg)


def test_fetch_all_paginates_and_retries(tmp_path):
    _CALLS.clear()
    server, client = _client()
    try:
        records = list(client.fetch_all())
    finally:
        server.shutdown()
    assert len(records) == len(RECORDS)
    assert records[0]["id"] == 1
    # page 1 was requested twice (503 -> retry), then pages 2, 3, 4(empty)
    assert len(_CALLS) >= 4


def test_fetch_to_jsonl_writes_one_record_per_line(tmp_path):
    server, client = _client()
    try:
        out = tmp_path / "events.jsonl"
        count = client.fetch_to_jsonl(out)
    finally:
        server.shutdown()
    assert count == len(RECORDS)
    lines = out.read_text().strip().splitlines()
    assert len(lines) == len(RECORDS)
    assert json.loads(lines[0])["id"] == 1


def test_missing_base_url_raises():
    try:
        PaginatedAPIClient(APIConfig(base_url=""))
    except ValueError as exc:
        assert "base_url" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty base_url")
