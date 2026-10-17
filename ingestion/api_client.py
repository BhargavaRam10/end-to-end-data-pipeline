"""Paginated REST API client with retry, used to ingest source events.

Reads configuration from environment (.env) so no credentials live in code:
  SERVICE_EVENTS_API_URL, SERVICE_EVENTS_API_KEY

Retry policy: exponential backoff on 429 / 5xx, fail fast on 4xx (except 429).
All raw responses are written to bronze as newline-delimited JSON with a
_load_timestamp column added downstream.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

DEFAULT_PAGE_SIZE = 100
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class APIConfig:
    base_url: str
    api_key: str | None = None
    page_size: int = DEFAULT_PAGE_SIZE
    max_retries: int = 3
    timeout_s: float = 30.0

    @classmethod
    def from_env(cls, prefix: str = "SERVICE_EVENTS") -> "APIConfig":
        return cls(
            base_url=os.environ.get(f"{prefix}_API_URL", ""),
            api_key=os.environ.get(f"{prefix}_API_KEY") or None,
        )


class APIClientError(Exception):
    """Raised when the API fails after all retries or fails fast on 4xx."""


class PaginatedAPIClient:
    def __init__(self, config: APIConfig) -> None:
        if not config.base_url:
            raise ValueError("API base_url is required (set SERVICE_EVENTS_API_URL)")
        self.config = config

    def _get(self, page: int) -> dict[str, Any]:
        url = f"{self.config.base_url}?page={page}&page_size={self.config.page_size}"
        req = urllib.request.Request(url)
        if self.config.api_key:
            req.add_header("Authorization", f"Bearer {self.config.api_key}")
        req.add_header("Accept", "application/json")

        attempt = 0
        while True:
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code in RETRYABLE_STATUS and attempt < self.config.max_retries:
                    attempt += 1
                    time.sleep(2**attempt)  # exponential backoff: 2s, 4s, 8s
                    continue
                raise APIClientError(
                    f"GET {url} failed with status {exc.code} after {attempt} retries"
                ) from exc
            except OSError as exc:  # connection errors are retryable
                if attempt < self.config.max_retries:
                    attempt += 1
                    time.sleep(2**attempt)
                    continue
                raise APIClientError(f"GET {url} failed: {exc}") from exc

    def fetch_all(self) -> Iterator[dict[str, Any]]:
        """Yield records across pages until the API returns an empty page."""
        page = 1
        while True:
            payload = self._get(page)
            records = payload.get("records", [])
            if not records:
                return
            yield from records
            page += 1

    def fetch_to_jsonl(self, output_path: Path) -> int:
        """Fetch every page and write newline-delimited JSON. Returns row count."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with output_path.open("w") as f:
            for record in self.fetch_all():
                f.write(json.dumps(record) + "\n")
                count += 1
        return count
