from __future__ import annotations

import os
from pathlib import Path

from .release_identity import find_root


APP_DIR_NAME = "Data Contract Monitor"


def runtime_root() -> Path:
    """Return the writable application root without relying on the current directory."""
    configured = os.environ.get("DCM_HOME") or os.environ.get("DCM_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    project = find_root(Path(__file__).resolve())
    if project is not None:
        return project
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / APP_DIR_NAME
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "data-contract-monitor"


def ensure_runtime_directories(root: Path | None = None) -> Path:
    target = (root or runtime_root()).resolve()
    for relative in (
        "logs",
        "state",
        "temp",
        "cache",
        "exports",
        "diagnostics/crash_capsules",
        "reports",
        "downloads",
        "backups",
    ):
        (target / relative).mkdir(parents=True, exist_ok=True)
    return target


def bundled_demo_contract() -> Path:
    """Return the packaged contract used by the credential-free demonstration."""
    project = find_root(Path(__file__).resolve())
    if project is not None:
        candidate = project / "examples" / "contracts" / "customer_orders.yml"
        if candidate.is_file():
            return candidate
    candidate = Path(__file__).resolve().parent / "resources" / "contracts" / "customer_orders.yml"
    if not candidate.is_file():
        raise FileNotFoundError("Bundled demonstration contract is missing")
    return candidate
