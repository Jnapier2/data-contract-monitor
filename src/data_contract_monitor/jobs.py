from __future__ import annotations

import shutil
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .artifacts import publish_run_artifacts
from .engine import ValidationCancelled, validate_files
from .limits import ResourceLimits
from .models import Severity
from .state_store import StateStore


class JobQueueFull(RuntimeError):
    """Raised when the bounded local validation queue has no capacity."""


class ValidationJobManager:
    def __init__(
        self,
        root: Path,
        *,
        max_workers: int = 1,
        queue_capacity: int = 4,
        limits: ResourceLimits | None = None,
    ) -> None:
        self.root = root.resolve()
        self.store = StateStore(self.root / "state" / "dcm_state.sqlite3")
        self.limits = limits or ResourceLimits()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dcm-validation")
        self._slots = threading.BoundedSemaphore(max_workers + queue_capacity)
        self._cancel: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[None]] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        *,
        contract_path: Path,
        data_path: Path,
        fail_on: Severity = Severity.ERROR,
        baseline_path: Path | None = None,
        object_name: str | None = None,
        sheet_name: str | int = 0,
        cleanup_dir: Path | None = None,
    ) -> str:
        if not self._slots.acquire(blocking=False):
            raise JobQueueFull("Validation queue is full. Try again after an active job finishes.")
        job_id = uuid.uuid4().hex
        event = threading.Event()
        self.store.create_job(job_id)
        with self._lock:
            self._cancel[job_id] = event
        future = self._executor.submit(
            self._run,
            job_id,
            contract_path,
            data_path,
            fail_on,
            baseline_path,
            object_name,
            sheet_name,
            event,
            cleanup_dir,
        )
        with self._lock:
            self._futures[job_id] = future
        return job_id

    def _run(
        self,
        job_id: str,
        contract_path: Path,
        data_path: Path,
        fail_on: Severity,
        baseline_path: Path | None,
        object_name: str | None,
        sheet_name: str | int,
        cancel_event: threading.Event,
        cleanup_dir: Path | None,
    ) -> None:
        try:
            self.store.update_job(job_id, state="preparing", progress=5, message="Preparing validation")

            def progress(stage: str, percent: int) -> None:
                self.store.update_job(job_id, state="running", progress=percent, message=stage.replace("_", " ").title())

            result = validate_files(
                contract_path=contract_path,
                data_path=data_path,
                baseline_path=baseline_path,
                fail_on=fail_on,
                object_name=object_name,
                sheet_name=sheet_name,
                history_path=self.store.path,
                limits=self.limits,
                progress=progress,
                cancelled=cancel_event.is_set,
            )
            if cancel_event.is_set():
                raise ValidationCancelled("Validation was cancelled before artifact publication.")
            self.store.update_job(job_id, state="reporting", progress=90, message="Publishing verified reports", run_id=result.run_id)
            artifact_dir = publish_run_artifacts(result, root=self.root)
            self.store.update_job(
                job_id,
                state="completed",
                progress=100,
                message="Validation complete",
                run_id=result.run_id,
                result=result.model_dump(mode="json"),
                artifact_dir=artifact_dir.relative_to(self.root).as_posix(),
            )
        except ValidationCancelled as exc:
            self.store.update_job(job_id, state="cancelled", progress=100, message="Cancelled", error=str(exc))
        except Exception as exc:
            self.store.update_job(job_id, state="failed", progress=100, message="Validation failed", error=str(exc))
        finally:
            if cleanup_dir is not None:
                shutil.rmtree(cleanup_dir, ignore_errors=True)
            with self._lock:
                self._cancel.pop(job_id, None)
                self._futures.pop(job_id, None)
            self._slots.release()

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            event = self._cancel.get(job_id)
        if event is None:
            return False
        event.set()
        current = self.store.get_job(job_id)
        if current and current["state"] == "queued":
            self.store.update_job(job_id, state="cancelling", message="Cancellation requested")
        return True

    def get(self, job_id: str) -> dict[str, Any] | None:
        return self.store.get_job(job_id)

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.list_jobs(limit=limit)

    def shutdown(self) -> None:
        with self._lock:
            for event in self._cancel.values():
                event.set()
        self._executor.shutdown(wait=True, cancel_futures=False)
