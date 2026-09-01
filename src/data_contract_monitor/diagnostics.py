from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import sys
import threading
import time
import traceback
import zipfile
from collections import deque
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .atomic import atomic_write_json
from .deployment_state import deployment_coherence
from .runtime import ensure_runtime_directories, runtime_root


_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*[^\s,;]+"
)
_SECRET_KEY_RE = re.compile(r"(?i)^(api[_-]?key|token|password|secret|authorization)$")
_EXPORT_NAME_RE = re.compile(
    r"^Data_Contract_Monitor_(?:Support|Critical)_\d{8}T\d{6}Z_[0-9a-f]{20}\.zip$"
)
_HOME_RE = re.compile(re.escape(str(Path.home())), re.I)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def redact(text: str) -> str:
    """Apply bounded best-effort redaction to diagnostic text."""
    value = _SECRET_RE.sub(r"\1=[REDACTED]", text)
    value = _HOME_RE.sub("[USER_HOME]", value)
    value = _IP_RE.sub("[IP_REDACTED]", value)
    return value[:20000]


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SECRET_KEY_RE.fullmatch(str(key)) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


def _candidate_payload(path: Path, mode: str) -> bytes | None:
    """Return a bounded archive payload, redacting runtime evidence when required."""
    if mode == "raw":
        return None
    if mode == "text":
        return (redact(path.read_text(encoding="utf-8", errors="replace")) + "\n").encode("utf-8")
    if mode in {"json", "latest-result"}:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if mode == "latest-result" and isinstance(payload, dict):
            payload["contract_label"] = "[REDACTED_FILENAME]"
            payload["data_label"] = "[REDACTED_FILENAME]"
        return (json.dumps(_redact_value(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
    raise ValueError(f"Unknown diagnostic archive mode: {mode}")


class RingBufferHandler(logging.Handler):
    def __init__(self, capacity: int = 200) -> None:
        super().__init__()
        self.records: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(redact(self.format(record)))
        except Exception:
            return


_RING = RingBufferHandler()
_CONFIGURED_ROOTS: set[Path] = set()


def configure_logging(root: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("data_contract_monitor")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    if _RING not in logger.handlers:
        _RING.setFormatter(formatter)
        logger.addHandler(_RING)
    target = ensure_runtime_directories(root or runtime_root())
    normalized = target.resolve()
    if normalized not in _CONFIGURED_ROOTS:
        file_handler = RotatingFileHandler(
            normalized / "logs" / "data_contract_monitor.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        _CONFIGURED_ROOTS.add(normalized)
    return logger


def _fingerprint(trigger: str, exc: BaseException | None) -> str:
    parts = [trigger]
    if exc:
        parts.extend([type(exc).__name__, re.sub(r"\d+", "#", str(exc))[:500]])
        tb = traceback.extract_tb(exc.__traceback__)
        if tb:
            last = tb[-1]
            parts.extend([Path(last.filename).name, last.name])
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def _cached_runtime_identity(root: Path) -> dict[str, Any]:
    """Read cached release identity only; crash collection never rehashes managed files."""
    receipt = root / "state" / "release_verification.json"
    if receipt.is_file():
        try:
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    version = None
    build_id = None
    try:
        version = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    try:
        metadata = json.loads((root / "PACKAGE_METADATA.json").read_text(encoding="utf-8"))
        build_id = metadata.get("build_id")
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    return {
        "mode": "release-unverified" if (root / "RELEASE_MODE").exists() else "source",
        "passed": None,
        "version": version,
        "build_id": build_id,
        "note": "No cached release-verification receipt was available; no rehash was attempted during diagnostics.",
    }


class DiagnosticManager:
    """Bounded, redacted diagnostics for terminal Critical failures and manual support exports."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = ensure_runtime_directories(root or runtime_root())
        self.logger = configure_logging(self.root)
        self.run_id = os.environ.get("DCM_RUN_ID") or hashlib.sha256(
            f"{os.getpid()}-{time.time_ns()}".encode()
        ).hexdigest()[:16]
        self._capturing = False
        self._seen: set[str] = set()

    def capture_critical(
        self,
        trigger: str,
        exc: BaseException | None = None,
        *,
        last_progress: str = "unknown",
    ) -> Path | None:
        if self._capturing:
            return None
        self._capturing = True
        started = time.monotonic()
        fingerprint = _fingerprint(trigger, exc)
        try:
            if fingerprint in self._seen:
                self._record_suppression(fingerprint)
                return None
            self._seen.add(fingerprint)
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            capsule_path = (
                self.root
                / "diagnostics"
                / "crash_capsules"
                / f"critical_{timestamp}_{fingerprint}.json"
            )
            payload: dict[str, Any] = {
                "schema_version": "1.0",
                "project": "Data Contract Monitor",
                "run_id": self.run_id,
                "created_at": datetime.now(UTC).isoformat(),
                "trigger": trigger,
                "severity": "critical",
                "fingerprint": fingerprint,
                "last_progress": last_progress,
                "exception_type": type(exc).__name__ if exc else None,
                "exception_message": redact(str(exc)) if exc else None,
                "traceback": redact("".join(traceback.format_exception(exc))[-20000:]) if exc else None,
                "log_tail": list(_RING.records)[-100:],
                "runtime_identity": _cached_runtime_identity(self.root),
                "deployment_coherence": deployment_coherence(self.root),
                "export_result": "capsule-written",
            }
            atomic_write_json(capsule_path, payload)
            export_path, reason = self._full_export(
                context_path=capsule_path,
                fingerprint=fingerprint,
                started=started,
                label="Critical",
            )
            payload["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            payload["export_result"] = "completed" if export_path else "capsule-only"
            payload["export_path"] = export_path.name if export_path else None
            payload["export_failure_reason"] = reason
            atomic_write_json(capsule_path, payload)
            self._retention()
            return export_path or capsule_path
        except Exception as export_exc:
            self.logger.error("Critical diagnostic capture failed: %s", redact(str(export_exc)))
            return None
        finally:
            self._capturing = False

    def create_manual_export(self) -> Path | None:
        """Create a requested support package without recording a false Critical incident."""
        if self._capturing:
            return None
        self._capturing = True
        started = time.monotonic()
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        fingerprint = _fingerprint("manual-support-export", None)
        context_path = self.root / "diagnostics" / f".support_context_{timestamp}.tmp.json"
        try:
            atomic_write_json(
                context_path,
                {
                    "schema_version": "1.0",
                    "project": "Data Contract Monitor",
                    "run_id": self.run_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "trigger": "manual-support-export",
                    "severity": "support",
                    "runtime_identity": _cached_runtime_identity(self.root),
                    "deployment_coherence": deployment_coherence(self.root),
                    "capture_note": "LATEST_LAUNCH_STATUS.txt is captured while the export action is still running; deployment_coherence is the authoritative current-vs-cached identity summary.",
                    "log_tail": list(_RING.records)[-100:],
                },
            )
            export_path, _ = self._full_export(
                context_path=context_path,
                fingerprint=fingerprint,
                started=started,
                label="Support",
            )
            self._retention()
            return export_path
        except Exception as export_exc:
            self.logger.error("Manual support export failed: %s", redact(str(export_exc)))
            return None
        finally:
            context_path.unlink(missing_ok=True)
            self._capturing = False

    def _record_suppression(self, fingerprint: str) -> None:
        path = self.root / "diagnostics" / "suppression_counts.json"
        payload: dict[str, Any] = {}
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        item = payload.setdefault(fingerprint, {"count": 0})
        item["count"] = int(item.get("count", 0)) + 1
        item["last_suppressed_at"] = datetime.now(UTC).isoformat()
        atomic_write_json(path, payload)

    def _full_export(
        self,
        *,
        context_path: Path,
        fingerprint: str,
        started: float,
        label: str,
    ) -> tuple[Path | None, str | None]:
        if time.monotonic() - started > 2.0:
            return None, "time budget exhausted before export"
        diagnostics = self.root / "diagnostics"
        export_dir = self.root / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        lock = diagnostics / ".export.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            return None, "another exporter is active on this computer"
        environment_path = diagnostics / f".environment_{self.run_id}.tmp.json"
        try:
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            final_path = export_dir / f"Data_Contract_Monitor_{label}_{timestamp}_{fingerprint}.zip"
            staging_dir = self.root / "temp"
            staging_dir.mkdir(parents=True, exist_ok=True)
            temporary = staging_dir / f".{final_path.name}.{self.run_id}.tmp"
            atomic_write_json(
                environment_path,
                {
                    "schema_version": "1.0",
                    "python": platform.python_version(),
                    "implementation": platform.python_implementation(),
                    "operating_system": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                    "run_id": self.run_id,
                    "captured_at": datetime.now(UTC).isoformat(),
                },
            )

            latest_capsule = None
            capsule_candidates = list((diagnostics / "crash_capsules").glob("*.json"))
            if capsule_candidates:
                latest_capsule = max(capsule_candidates, key=lambda item: item.stat().st_mtime)

            latest_pointer = self.root / "state" / "latest_completed_run.json"
            latest_result = None
            try:
                pointer = json.loads(latest_pointer.read_text(encoding="utf-8"))
                artifact_dir = pointer.get("artifact_dir") if isinstance(pointer, dict) else None
                if isinstance(artifact_dir, str):
                    candidate = (self.root / artifact_dir / "result.json").resolve()
                    runs_root = (self.root / "reports" / "runs").resolve()
                    if candidate.is_relative_to(runs_root) and candidate.is_file():
                        latest_result = candidate
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                latest_result = None

            candidates: list[tuple[Path, str]] = [
                (context_path, "json"),
                (self.root / "LATEST_LAUNCH_STATUS.txt", "text"),
                (self.root / "state" / "latest_launch_status.json", "json"),
                (self.root / "state" / "dashboard_endpoint.json", "json"),
                (self.root / "logs" / "launcher.log", "text"),
                (self.root / "logs" / "bootstrap.log", "text"),
                (self.root / "logs" / "python_detection.txt", "text"),
                (self.root / "logs" / "data_contract_monitor.log", "text"),
                (self.root / "state" / "runtime_environment.json", "json"),
                (self.root / "state" / "release_verification.json", "json"),
                (self.root / "state" / "latest_completed_run.json", "json"),
                (self.root / "VERSION.txt", "raw"),
                (self.root / "PACKAGE_METADATA.json", "raw"),
                (self.root / "MANIFEST.json", "raw"),
                (self.root / "MANIFEST.sha256", "raw"),
                (self.root / "KNOWN_GOOD_STATE.md", "raw"),
                (self.root / "CHANGELOG.md", "raw"),
                (environment_path, "json"),
            ]
            if latest_capsule is not None:
                candidates.insert(10, (latest_capsule, "json"))
            if latest_result is not None:
                candidates.insert(11, (latest_result, "latest-result"))

            added = 0
            total = 0
            seen: set[Path] = set()
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for candidate, mode in candidates:
                    if added >= 20 or time.monotonic() - started > 4.0:
                        break
                    if not candidate.is_file():
                        continue
                    resolved = candidate.resolve()
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    source_size = candidate.stat().st_size
                    if source_size > 2 * 1024 * 1024:
                        continue

                    if candidate == context_path:
                        arcname = (
                            "diagnostics/critical_context.json"
                            if label == "Critical"
                            else "diagnostics/support_context.json"
                        )
                    elif candidate == environment_path:
                        arcname = "diagnostics/environment_summary.json"
                    elif mode == "latest-result":
                        arcname = "reports/latest_result.redacted.json"
                    elif candidate.is_relative_to(self.root):
                        arcname = candidate.relative_to(self.root).as_posix()
                    else:
                        arcname = candidate.name

                    try:
                        payload = _candidate_payload(candidate, mode)
                    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                        continue
                    archived_size = source_size if payload is None else len(payload)
                    if archived_size > 2 * 1024 * 1024 or total + archived_size > 5 * 1024 * 1024:
                        continue
                    if payload is None:
                        archive.write(candidate, arcname=arcname)
                    else:
                        archive.writestr(arcname, payload)
                    added += 1
                    total += archived_size

            with zipfile.ZipFile(temporary, "r") as archive:
                names = archive.namelist()
                if (
                    archive.testzip() is not None
                    or not names
                    or len(names) > 20
                    or len(names) != len(set(names))
                ):
                    temporary.unlink(missing_ok=True)
                    return None, "ZIP integrity, uniqueness, or entry-count test failed"
            os.replace(temporary, final_path)
            return final_path, None
        finally:
            environment_path.unlink(missing_ok=True)
            lock.unlink(missing_ok=True)

    def _retention(self) -> None:
        export_dir = self.root / "exports"
        if not export_dir.exists():
            return
        files = sorted(
            (
                path
                for path in export_dir.glob("Data_Contract_Monitor_*.zip")
                if _EXPORT_NAME_RE.fullmatch(path.name)
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        cutoff = datetime.now(UTC) - timedelta(days=30)
        total = 0
        for index, path in enumerate(files):
            size = path.stat().st_size
            modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            total += size
            if index >= 5 or modified < cutoff or total > 25 * 1024 * 1024:
                path.unlink(missing_ok=True)


def install_exception_hooks(manager: DiagnosticManager) -> None:
    original = sys.excepthook

    def hook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        exc.__traceback__ = tb
        manager.capture_critical("uncaught-fatal-exception", exc)
        original(exc_type, exc, tb)

    sys.excepthook = hook

    if hasattr(threading, "excepthook"):
        original_thread = threading.excepthook

        def thread_hook(args: threading.ExceptHookArgs) -> None:
            manager.capture_critical("uncaught-thread-exception", args.exc_value)
            original_thread(args)

        threading.excepthook = thread_hook
