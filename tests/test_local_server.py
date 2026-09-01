from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

import data_contract_monitor.local_server as local_server
from data_contract_monitor.local_server import (
    SERVICE_ID,
    PortReservationError,
    ReservedEndpoint,
    health_matches,
    open_browser_when_ready,
    record_endpoint,
    reserve_endpoint,
)


def test_port_collision_uses_bounded_fallback() -> None:
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    preferred = occupied.getsockname()[1]
    occupied.listen(1)
    try:
        endpoint = reserve_endpoint("127.0.0.1", preferred, search_limit=3)
        try:
            assert endpoint.port != preferred
            assert preferred < endpoint.port <= preferred + 3
            assert endpoint.fallback_used is True
        finally:
            endpoint.socket.close()
    finally:
        occupied.close()



def test_exhausted_bounded_range_uses_reserved_os_assigned_port(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_bind(host: str, port: int) -> socket.socket:
        calls.append(port)
        if port != 0:
            raise OSError("occupied")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, 0))
        return sock

    monkeypatch.setattr(local_server, "_bind", fake_bind)
    endpoint = reserve_endpoint("127.0.0.1", 8765, search_limit=2)
    try:
        assert calls == [8765, 8766, 8767, 0]
        assert endpoint.port not in {8765, 8766, 8767}
        assert endpoint.fallback_used is True
    finally:
        endpoint.socket.close()


def test_zero_search_limit_requires_exact_port() -> None:
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    preferred = occupied.getsockname()[1]
    occupied.listen(1)
    try:
        with pytest.raises(PortReservationError):
            reserve_endpoint("127.0.0.1", preferred, search_limit=0)
    finally:
        occupied.close()

def test_exact_health_identity_is_required_before_browser_open() -> None:
    calls: list[str] = []
    payloads = iter(
        [
            {"service_id": "btc-miner", "version": "0.2.1", "build_id": "expected"},
            {"service_id": SERVICE_ID, "version": "0.1.1", "build_id": "old"},
            {"service_id": SERVICE_ID, "version": "0.2.1", "build_id": "expected"},
        ]
    )

    def reader(_: str) -> dict[str, str] | None:
        return next(payloads, None)

    opened = open_browser_when_ready(
        "http://127.0.0.1:8765",
        expected_version="0.2.1",
        expected_build_id="expected",
        timeout_seconds=0.2,
        poll_seconds=0.01,
        health_reader=reader,
        browser_opener=lambda url: calls.append(url),
    )
    assert opened is True
    assert calls == ["http://127.0.0.1:8765/?build=expected"]


def test_wrong_service_never_opens_browser() -> None:
    calls: list[str] = []
    opened = open_browser_when_ready(
        "http://127.0.0.1:8765",
        expected_version="0.2.1",
        expected_build_id="expected",
        timeout_seconds=0.03,
        poll_seconds=0.01,
        health_reader=lambda _: {
            "service_id": "btc-miner",
            "version": "0.2.1",
            "build_id": "expected",
        },
        browser_opener=lambda url: calls.append(url),
    )
    assert opened is False
    assert calls == []


def test_health_match_requires_service_version_build_and_launch_identity() -> None:
    expected = {
        "service_id": SERVICE_ID,
        "version": "0.2.1",
        "build_id": "build",
        "launch_id": "launch-a",
    }
    assert health_matches(
        expected,
        expected_version="0.2.1",
        expected_build_id="build",
        expected_launch_id="launch-a",
    )
    for key in ("service_id", "version", "build_id", "launch_id"):
        wrong = dict(expected)
        wrong[key] = "wrong"
        assert not health_matches(
            wrong,
            expected_version="0.2.1",
            expected_build_id="build",
            expected_launch_id="launch-a",
        )


def test_endpoint_record_contains_actual_fallback_url(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "LATEST_LAUNCH_STATUS.txt").write_text(
        "Data Contract Monitor startup status\nState: running\n", encoding="utf-8"
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    endpoint = ReservedEndpoint(
        host="127.0.0.1",
        preferred_port=8765,
        port=8766,
        socket=sock,
    )
    try:
        path = record_endpoint(
            tmp_path,
            endpoint,
            version="0.2.1",
            build_id="DCM-0.2.1-TEST",
            state="starting",
            launch_id="test-launch",
            browser_status="waiting-for-verified-identity",
            note="preferred port occupied",
        )
    finally:
        sock.close()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["service_id"] == SERVICE_ID
    assert payload["fallback_used"] is True
    assert payload["url"] == "http://127.0.0.1:8766"
    assert payload["browser_url"] == "http://127.0.0.1:8766/?build=DCM-0.2.1-TEST"
    status = (tmp_path / "LATEST_LAUNCH_STATUS.txt").read_text(encoding="utf-8")
    assert "Dashboard URL: http://127.0.0.1:8766" in status
    assert "Browser URL: http://127.0.0.1:8766/?build=DCM-0.2.1-TEST" in status
    assert "Port fallback: yes" in status
