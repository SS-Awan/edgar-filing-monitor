from datetime import date
from hashlib import sha256

import httpx
import pytest

from edgar_monitor.sec_client import (
    SourceFetchError,
    build_daily_master_index_url,
    create_sec_client,
    fetch_daily_master_index,
)


class FakeClient:
    """Small test-only HTTP client that returns predefined responses."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str) -> httpx.Response:
        self.urls.append(url)
        return self.responses.pop(0)


def make_response(status_code: int, text: str = "") -> httpx.Response:
    request = httpx.Request("GET", "https://example.test")
    return httpx.Response(status_code, text=text, request=request)


def test_build_daily_master_index_url_uses_correct_quarter() -> None:
    source_url = build_daily_master_index_url(date(2026, 9, 10))

    assert source_url == (
        "https://www.sec.gov/Archives/edgar/daily-index/"
        "2026/QTR3/master.20260910.idx"
    )


def test_fetch_daily_master_index_records_checksum_and_provenance() -> None:
    payload = "CIK|Company Name|Form Type|Date Filed|Filename\n"
    client = FakeClient([make_response(200, payload)])

    fetched = fetch_daily_master_index(date(2026, 9, 10), client)  # type: ignore[arg-type]

    assert fetched.payload == payload
    assert fetched.payload_sha256 == sha256(payload.encode("utf-8")).hexdigest()
    assert fetched.payload_bytes == len(payload.encode("utf-8"))
    assert fetched.attempts == 1
    assert client.urls == [fetched.source_url]


def test_fetch_daily_master_index_retries_temporary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("edgar_monitor.sec_client.sleep", lambda _: None)

    client = FakeClient(
        [
            make_response(503),
            make_response(200, "CIK|Company Name|Form Type|Date Filed|Filename\n"),
        ]
    )

    fetched = fetch_daily_master_index(date(2026, 9, 10), client)  # type: ignore[arg-type]

    assert fetched.attempts == 2
    assert len(client.urls) == 2


def test_fetch_daily_master_index_does_not_retry_not_found() -> None:
    client = FakeClient([make_response(404)])

    with pytest.raises(SourceFetchError, match="after 1 attempt"):
        fetch_daily_master_index(date(2026, 9, 10), client)  # type: ignore[arg-type]


def test_create_sec_client_rejects_blank_user_agent() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        create_sec_client("   ")