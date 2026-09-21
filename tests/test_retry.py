from __future__ import annotations

import pytest

from garminconnect import GarminConnectAuthenticationError, GarminConnectConnectionError
from garmin_tracker.retry import call_with_retry


def test_call_with_retry_succeeds_first_try() -> None:
    calls: list[int] = []

    def fn() -> str:
        calls.append(1)
        return "ok"

    assert call_with_retry(fn, max_attempts=3, base_delay=0.01) == "ok"
    assert len(calls) == 1


def test_call_with_retry_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("garmin_tracker.retry.time.sleep", lambda _seconds: None)
    attempts = {"n": 0}

    def fn() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise GarminConnectConnectionError("boom")
        return "ok"

    assert call_with_retry(fn, max_attempts=5, base_delay=0.01) == "ok"
    assert attempts["n"] == 3


def test_call_with_retry_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("garmin_tracker.retry.time.sleep", lambda _seconds: None)

    def fn() -> str:
        raise GarminConnectConnectionError("boom")

    with pytest.raises(GarminConnectConnectionError):
        call_with_retry(fn, max_attempts=3, base_delay=0.01)


def test_call_with_retry_does_not_retry_auth_errors() -> None:
    calls: list[int] = []

    def fn() -> str:
        calls.append(1)
        raise GarminConnectAuthenticationError("bad creds")

    with pytest.raises(GarminConnectAuthenticationError):
        call_with_retry(fn, max_attempts=5, base_delay=0.01)
    assert len(calls) == 1
