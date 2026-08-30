from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic import atomic_write_text, sha256_file
from .models import ValidationResult

SCHEMA_VERSION = 1


class StateStoreError(RuntimeError):
    """Raised when the durable local state cannot be initialized or queried."""


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        existed = self.path.exists()
        try:
            with self._connect() as connection:
                current = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if current > SCHEMA_VERSION:
                    raise StateStoreError(
                        f"State schema {current} is newer than supported schema {SCHEMA_VERSION}."
                    )
                if existed and current < SCHEMA_VERSION:
                    self._backup_before_migration(connection, current)
                if current < 1:
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS validation_runs (
                            run_id TEXT PRIMARY KEY,
                            dataset_name TEXT NOT NULL,
                            started_at TEXT NOT NULL,
                            completed_at TEXT NOT NULL,
                            duration_ms INTEGER NOT NULL,
                            status TEXT NOT NULL,
                            findings_total INTEGER NOT NULL,
                            warnings INTEGER NOT NULL,
                            errors INTEGER NOT NULL,
                            critical INTEGER NOT NULL,
                            row_count INTEGER NOT NULL,
                            column_count INTEGER NOT NULL,
                            contract_sha256 TEXT NOT NULL,
                            data_sha256 TEXT NOT NULL,
                            result_json TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS findings (
                            run_id TEXT NOT NULL REFERENCES validation_runs(run_id) ON DELETE CASCADE,
                            finding_index INTEGER NOT NULL,
                            finding_id TEXT NOT NULL,
                            severity TEXT NOT NULL,
                            category TEXT NOT NULL,
                            rule_id TEXT NOT NULL,
                            column_name TEXT,
                            PRIMARY KEY (run_id, finding_index)
                        );
                        CREATE TABLE IF NOT EXISTS jobs (
                            job_id TEXT PRIMARY KEY,
                            state TEXT NOT NULL,
                            progress INTEGER NOT NULL,
                            message TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            run_id TEXT,
                            result_json TEXT,
                            artifact_dir TEXT,
                            error TEXT
                        );
                        CREATE INDEX IF NOT EXISTS idx_runs_started_at ON validation_runs(started_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_jobs_updated_at ON jobs(updated_at DESC);
                        PRAGMA user_version=1;
                        """
                    )
        except sqlite3.Error as exc:
            raise StateStoreError(f"Unable to initialize state database: {exc}") from exc

    def _backup_before_migration(
        self, connection: sqlite3.Connection, from_version: int
    ) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        backups = self.path.parent.parent / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = backups / f"state_schema_{from_version}_before_{SCHEMA_VERSION}_{stamp}.sqlite3"
        destination = sqlite3.connect(target)
        try:
            connection.backup(destination)
        finally:
            destination.close()
        check = sqlite3.connect(target)
        try:
            integrity = str(check.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            check.close()
        if integrity.lower() != "ok":
            target.unlink(missing_ok=True)
            raise StateStoreError(f"State migration backup failed integrity check: {integrity}")
        atomic_write_text(
            target.with_suffix(target.suffix + ".sha256.txt"),
            f"{sha256_file(target)}  {target.name}\n",
        )

    def record_validation(self, result: ValidationResult) -> None:
        payload = result.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO validation_runs
                (run_id,dataset_name,started_at,completed_at,duration_ms,status,findings_total,warnings,errors,critical,row_count,column_count,contract_sha256,data_sha256,result_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    result.run_id,
                    result.dataset_name,
                    result.started_at.isoformat(),
                    result.completed_at.isoformat(),
                    result.duration_ms,
                    result.summary.status,
                    result.summary.findings_total,
                    result.summary.warnings,
                    result.summary.errors,
                    result.summary.critical,
                    result.profile.row_count,
                    result.profile.column_count,
                    result.contract_sha256,
                    result.data_sha256,
                    payload,
                ),
            )
            connection.execute("DELETE FROM findings WHERE run_id=?", (result.run_id,))
            connection.executemany(
                """
                INSERT INTO findings(run_id,finding_index,finding_id,severity,category,rule_id,column_name)
                VALUES (?,?,?,?,?,?,?)
                """,
                [
                    (
                        result.run_id,
                        index,
                        finding.id,
                        finding.severity.value,
                        finding.category,
                        finding.rule_id,
                        finding.column,
                    )
                    for index, finding in enumerate(result.findings)
                ],
            )

    def read_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        bounded = min(max(int(limit), 1), 500)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id,dataset_name,started_at,duration_ms,status,findings_total,warnings,errors,critical,row_count,column_count,contract_sha256,data_sha256
                FROM validation_runs ORDER BY started_at DESC LIMIT ?
                """,
                (bounded,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_result(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM validation_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def create_job(self, job_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs(job_id,state,progress,message,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, "queued", 0, "Queued", now, now),
            )

    def update_job(
        self,
        job_id: str,
        *,
        state: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        run_id: str | None = None,
        result: dict[str, Any] | None = None,
        artifact_dir: str | None = None,
        error: str | None = None,
    ) -> None:
        current = self.get_job(job_id)
        if current is None:
            raise StateStoreError(f"Unknown job '{job_id}'.")
        now = datetime.now(UTC).isoformat()
        values = {
            "state": state if state is not None else current["state"],
            "progress": int(progress if progress is not None else current["progress"]),
            "message": message if message is not None else current["message"],
            "run_id": run_id if run_id is not None else current.get("run_id"),
            "result_json": json.dumps(result, sort_keys=True) if result is not None else current.get("result_json"),
            "artifact_dir": artifact_dir if artifact_dir is not None else current.get("artifact_dir"),
            "error": error if error is not None else current.get("error"),
        }
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET state=?,progress=?,message=?,updated_at=?,run_id=?,result_json=?,artifact_dir=?,error=? WHERE job_id=?
                """,
                (
                    values["state"], values["progress"], values["message"], now,
                    values["run_id"], values["result_json"], values["artifact_dir"], values["error"], job_id,
                ),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        if result.get("result_json"):
            result["result"] = json.loads(result["result_json"])
        result.pop("result_json", None)
        return result

    def list_jobs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        bounded = min(max(int(limit), 1), 100)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (bounded,)
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if item.get("result_json"):
                item["result"] = json.loads(item["result_json"])
            item.pop("result_json", None)
            results.append(item)
        return results

    def health_check(self) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                runs = int(connection.execute("SELECT COUNT(*) FROM validation_runs").fetchone()[0])
            return {"passed": integrity == "ok" and version == SCHEMA_VERSION, "integrity": integrity, "schema_version": version, "runs": runs}
        except sqlite3.Error:
            return {
                "passed": False,
                "error": "state_database_unavailable",
                "schema_version": None,
                "runs": None,
            }
