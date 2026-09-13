"""Fetch SEC EDGAR daily master-index files with bounded retries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from time import sleep

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class SourceFetchError(RuntimeError):
    """Raised when an SEC source cannot be fetched safely."""


@dataclass(frozen=True)
class FetchedSource:
    """One successfully downloaded source payload and its provenance."""

    source_date: date
    source_url: str
    payload: str
    payload_sha256: str
    payload_bytes: int
    fetched_at: datetime
    attempts: int


def build_daily_master_index_url(source_date: date) -> str:
    """Build the official SEC URL for a daily master-index file."""
    quarter = ((source_date.month - 1) // 3) + 1
    return (
        "https://www.sec.gov/Archives/edgar/daily-index/"
        f"{source_date.year}/QTR{quarter}/master.{source_date:%Y%m%d}.idx"
    )


def create_sec_client(user_agent: str, timeout_seconds: float = 20.0) -> httpx.Client:
    """Create an SEC-compliant HTTP client for a pipeline run."""
    if not user_agent.strip():
        raise ValueError("SEC user agent must not be blank.")

    return httpx.Client(
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        },
        follow_redirects=True,
        timeout=timeout_seconds,
    )


def fetch_daily_master_index(
    source_date: date,
    client: httpx.Client,
    max_attempts: int = 3,
) -> FetchedSource:
    """Fetch one SEC daily index and retry only temporary failures."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    source_url = build_daily_master_index_url(source_date)

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(source_url)
            response.raise_for_status()

            payload = response.text
            payload_bytes = len(payload.encode("utf-8"))

            return FetchedSource(
                source_date=source_date,
                source_url=source_url,
                payload=payload,
                payload_sha256=sha256(payload.encode("utf-8")).hexdigest(),
                payload_bytes=payload_bytes,
                fetched_at=datetime.now(UTC),
                attempts=attempt,
            )
        except httpx.HTTPError as error:
            is_retryable = (
                isinstance(error, httpx.RequestError)
                or (
                    isinstance(error, httpx.HTTPStatusError)
                    and error.response.status_code in RETRYABLE_STATUS_CODES
                )
            )

            if not is_retryable or attempt == max_attempts:
                raise SourceFetchError(
                    f"Could not fetch SEC index for {source_date} after {attempt} attempt(s)."
                ) from error

            sleep(2 ** (attempt - 1))

    raise AssertionError("Retry loop should always return or raise.")