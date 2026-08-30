"""Collision-safe local dashboard startup helpers.

The launcher must never open an unrelated service that happens to own the
preferred loopback port. This module reserves a socket first and allows browser
opening only after the responding health endpoint proves the expected product,
version, build, and per-launch identity.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic import atomic_write_json, atomic_write_text

SERVICE_ID = "data-contract-monitor"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_PORT_SEARCH_LIMIT = 20


class PortReservationError(RuntimeError):
    """Raised when no local dashboard port can be reserved."""


@dataclass
class ReservedEndpoint:
    """A bound socket and the endpoint selected for the dashboard."""

    host: str
    preferred_port: int
    port: int
    socket: socket.socket

    @property
    def fallback_used(self) -> bool:
        return self.port != self.preferred_port

    @property
    def url(self) -> str:
        display_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
        if display_host == "::":
            display_host = "::1"
        if ":" in display_host and not display_host.startswith("["):
            display_host = f"[{display_host}]"
        return f"http://{display_host}:{self.port}"


def _socket_family(host: str) -> socket.AddressFamily:
    return socket.AF_INET6 if ":" in host else socket.AF_INET


def _configure_reservation_socket(sock: socket.socket) -> None:
    # Windows otherwise permits surprising address reuse semantics. Reserving the
    # socket exclusively prevents an unrelated local service from owning the URL
    # that the browser receives.
    if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    sock.set_inheritable(True)


def _bind(host: str, port: int) -> socket.socket:
    sock = socket.socket(_socket_family(host), socket.SOCK_STREAM)
    try:
        _configure_reservation_socket(sock)
        sock.bind((host, port))
        return sock
    except Exception:
        sock.close()
        raise


def reserve_endpoint(
    host: str,
    preferred_port: int,
    *,
    search_limit: int = DEFAULT_PORT_SEARCH_LIMIT,
) -> ReservedEndpoint:
    """Reserve the preferred port, a bounded fallback, or an OS-assigned port.

    The returned socket remains open until handed to Uvicorn. This removes the
    check-then-bind race that caused v0.1.1 to open another local application's
    page when port 8765 was already occupied.
    """

    if not 1 <= preferred_port <= 65535:
        raise ValueError("preferred_port must be between 1 and 65535")
    if search_limit < 0:
        raise ValueError("search_limit cannot be negative")

    last_error: OSError | None = None
    final_port = min(65535, preferred_port + search_limit)
    for candidate in range(preferred_port, final_port + 1):
        try:
            sock = _bind(host, candidate)
        except OSError as exc:
            last_error = exc
            continue
        return ReservedEndpoint(host=host, preferred_port=preferred_port, port=candidate, socket=sock)

    if search_limit == 0:
        detail = f": {last_error}" if last_error else ""
        raise PortReservationError(f"Requested dashboard port {preferred_port} is unavailable{detail}")

    # A crowded fixed range should not make the application unusable. Binding to
    # port zero asks the operating system for an available local port while the
    # returned socket remains reserved.
    try:
        sock = _bind(host, 0)
    except OSError as exc:
        error_detail = last_error or exc
        raise PortReservationError(
            f"No local dashboard port could be reserved: {error_detail}"
        ) from exc
    selected = int(sock.getsockname()[1])
    return ReservedEndpoint(host=host, preferred_port=preferred_port, port=selected, socket=sock)


def health_matches(
    payload: Any,
    *,
    expected_version: str,
    expected_build_id: str,
    expected_launch_id: str | None = None,
) -> bool:
    """Return True only for this exact Data Contract Monitor process identity."""

    return bool(
        isinstance(payload, dict)
        and payload.get("service_id") == SERVICE_ID
        and payload.get("version") == expected_version
        and payload.get("build_id") == expected_build_id
        and (
            expected_launch_id is None
            or payload.get("launch_id") == expected_launch_id
        )
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def read_health(url: str, *, timeout: float = 2.0) -> dict[str, Any] | None:
    """Read the loopback health endpoint without using configured HTTP proxies."""

    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/health",
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "DataContractMonitor-Launcher",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
        urllib.request.HTTPHandler(),
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read(64 * 1024).decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError):
        return None


def open_browser_when_ready(
    url: str,
    *,
    expected_version: str,
    expected_build_id: str,
    expected_launch_id: str | None = None,
    timeout_seconds: float = 20.0,
    poll_seconds: float = 0.2,
    health_reader: Callable[[str], dict[str, Any] | None] | None = None,
    browser_opener: Callable[[str], Any] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> bool:
    """Open the browser only after the endpoint proves the expected identity."""

    reader = health_reader or read_health
    opener = browser_opener or webbrowser.open_new_tab
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() <= deadline:
        if cancelled is not None and cancelled():
            return False
        payload = reader(url)
        if health_matches(
            payload,
            expected_version=expected_version,
            expected_build_id=expected_build_id,
            expected_launch_id=expected_launch_id,
        ):
            if cancelled is not None and cancelled():
                return False
            result = opener(url)
            return result is not False
        time.sleep(max(0.01, poll_seconds))
    return False



def record_endpoint(
    root: Path,
    endpoint: ReservedEndpoint,
    *,
    version: str,
    build_id: str,
    state: str,
    launch_id: str,
    browser_status: str,
    note: str | None = None,
) -> Path:
    """Record the selected endpoint and update human-readable launch status."""

    payload: dict[str, Any] = {
        "schema_version": "1.1",
        "service_id": SERVICE_ID,
        "name": "Data Contract Monitor",
        "version": version,
        "build_id": build_id,
        "launch_id": launch_id,
        "state": state,
        "host": endpoint.host,
        "preferred_port": endpoint.preferred_port,
        "selected_port": endpoint.port,
        "fallback_used": endpoint.fallback_used,
        "url": endpoint.url,
        "browser_status": browser_status,
        "process_id": os.getpid(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if note:
        payload["note"] = note
    destination = root / "state" / "dashboard_endpoint.json"
    atomic_write_json(destination, payload)

    status_path = root / "LATEST_LAUNCH_STATUS.txt"
    try:
        existing = status_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        existing = ["Data Contract Monitor startup status"]
    prefixes = (
        "Dashboard state:",
        "Dashboard URL:",
        "Preferred port:",
        "Selected port:",
        "Port fallback:",
        "Browser status:",
        "Dashboard note:",
    )
    retained = [line for line in existing if not line.startswith(prefixes)]
    retained.extend(
        [
            f"Dashboard state: {state}",
            f"Dashboard URL: {endpoint.url}",
            f"Preferred port: {endpoint.preferred_port}",
            f"Selected port: {endpoint.port}",
            f"Port fallback: {'yes' if endpoint.fallback_used else 'no'}",
            f"Browser status: {browser_status}",
        ]
    )
    if note:
        retained.append(f"Dashboard note: {note}")
    atomic_write_text(status_path, "\n".join(retained) + "\n")
    return destination
