from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic import atomic_write_text, sha256_file
from .models import ValidationResult

SCHEMA_VERSION = 3


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

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        existed = self.path.exists()
        try:
            with self._connection() as connection:
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
                    current = 1
                if current < 2:
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS contract_versions (
                            contract_sha256 TEXT PRIMARY KEY,
                            dataset_name TEXT NOT NULL,
                            contract_version TEXT,
                            source_format TEXT NOT NULL,
                            first_seen_at TEXT NOT NULL,
                            last_seen_at TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS dataset_profiles (
                            run_id TEXT PRIMARY KEY REFERENCES validation_runs(run_id) ON DELETE CASCADE,
                            profile_json TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS drift_events (
                            run_id TEXT NOT NULL REFERENCES validation_runs(run_id) ON DELETE CASCADE,
                            change_index INTEGER NOT NULL,
                            change_type TEXT NOT NULL,
                            column_name TEXT NOT NULL,
                            severity TEXT NOT NULL,
                            before_value TEXT,
                            after_value TEXT,
                            PRIMARY KEY (run_id, change_index)
                        );
                        CREATE TABLE IF NOT EXISTS run_artifacts (
                            run_id TEXT NOT NULL REFERENCES validation_runs(run_id) ON DELETE CASCADE,
                            path TEXT NOT NULL,
                            sha256 TEXT NOT NULL,
                            size INTEGER NOT NULL,
                            PRIMARY KEY (run_id, path)
                        );
                        CREATE INDEX IF NOT EXISTS idx_contract_dataset ON contract_versions(dataset_name,last_seen_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_drift_run ON drift_events(run_id,change_index);
                        PRAGMA user_version=2;
                        """
                    )
                    current = 2
                if current < 3:
                    columns = {
                        str(row[1])
                        for row in connection.execute("PRAGMA table_info(contract_versions)").fetchall()
                    }
                    if "contract_id" not in columns:
                        connection.execute("ALTER TABLE contract_versions ADD COLUMN contract_id TEXT")
                    connection.execute("PRAGMA user_version=3")
                    current = 3
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
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
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
            connection.execute(
                """
                INSERT INTO contract_versions(contract_sha256,dataset_name,contract_id,contract_version,source_format,first_seen_at,last_seen_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(contract_sha256) DO UPDATE SET
                    contract_id=excluded.contract_id,
                    contract_version=excluded.contract_version,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    result.contract_sha256,
                    result.dataset_name,
                    result.contract_id,
                    result.contract_version,
                    result.source_format,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT OR REPLACE INTO dataset_profiles(run_id,profile_json) VALUES(?,?)",
                (result.run_id, result.profile.model_dump_json()),
            )
            connection.execute("DELETE FROM drift_events WHERE run_id=?", (result.run_id,))
            connection.executemany(
                """
                INSERT INTO drift_events(run_id,change_index,change_type,column_name,severity,before_value,after_value)
                VALUES(?,?,?,?,?,?,?)
                """,
                [
                    (
                        result.run_id,
                        index,
                        change.change_type,
                        change.column,
                        change.severity.value,
                        None if change.before is None else str(change.before),
                        None if change.after is None else str(change.after),
                    )
                    for index, change in enumerate(result.drift.changes)
                ],
            )

    def record_artifacts(self, run_id: str, entries: list[dict[str, Any]]) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM run_artifacts WHERE run_id=?", (run_id,))
            connection.executemany(
                "INSERT INTO run_artifacts(run_id,path,sha256,size) VALUES(?,?,?,?)",
                [
                    (run_id, str(entry["path"]), str(entry["sha256"]), int(entry["size"]))
                    for entry in entries
                ],
            )

    def read_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        bounded = min(max(int(limit), 1), 500)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT run_id,dataset_name,started_at,duration_ms,status,findings_total,warnings,errors,critical,row_count,column_count,contract_sha256,data_sha256
                FROM validation_runs ORDER BY started_at DESC LIMIT ?
                """,
                (bounded,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_result(self, run_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT result_json FROM validation_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def compare_runs(self, older_run_id: str, newer_run_id: str) -> dict[str, Any]:
        older = self.get_result(older_run_id)
        newer = self.get_result(newer_run_id)
        if older is None or newer is None:
            missing = older_run_id if older is None else newer_run_id
            raise StateStoreError(f"Unknown run '{missing}'.")
        older_findings = {item["id"]: item for item in older.get("findings", [])}
        newer_findings = {item["id"]: item for item in newer.get("findings", [])}
        return {
            "older_run_id": older_run_id,
            "newer_run_id": newer_run_id,
            "dataset_name": newer.get("dataset_name"),
            "status": {"before": older.get("summary", {}).get("status"), "after": newer.get("summary", {}).get("status")},
            "row_count_delta": int(newer.get("profile", {}).get("row_count", 0)) - int(older.get("profile", {}).get("row_count", 0)),
            "finding_count_delta": int(newer.get("summary", {}).get("findings_total", 0)) - int(older.get("summary", {}).get("findings_total", 0)),
            "new_findings": [newer_findings[key] for key in sorted(newer_findings.keys() - older_findings.keys())],
            "resolved_findings": [older_findings[key] for key in sorted(older_findings.keys() - newer_findings.keys())],
            "persistent_findings": sorted(older_findings.keys() & newer_findings.keys()),
            "contract_changed": older.get("contract_sha256") != newer.get("contract_sha256"),
            "data_changed": older.get("data_sha256") != newer.get("data_sha256"),
        }

    def trend(self, *, dataset_name: str | None = None, limit: int = 50) -> dict[str, Any]:
        bounded = min(max(int(limit), 2), 500)
        query = """
            SELECT run_id,dataset_name,started_at,status,findings_total,warnings,errors,critical,row_count,duration_ms
            FROM validation_runs
        """
        params: list[Any] = []
        if dataset_name:
            query += " WHERE dataset_name=?"
            params.append(dataset_name)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(bounded)
        with self._connection() as connection:
            rows = [dict(row) for row in connection.execute(query, params).fetchall()]
            drift_rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT d.run_id,d.change_type,d.column_name,d.severity,r.started_at,r.dataset_name
                    FROM drift_events d JOIN validation_runs r ON r.run_id=d.run_id
                    ORDER BY r.started_at DESC LIMIT ?
                    """,
                    (bounded * 20,),
                ).fetchall()
                if dataset_name is None or str(row[5]) == dataset_name
            ]
        chronological = list(reversed(rows))
        pass_count = sum(1 for row in rows if row["status"] == "passed")
        return {
            "dataset_name": dataset_name,
            "runs": chronological,
            "run_count": len(rows),
            "pass_rate": round(pass_count / len(rows), 6) if rows else None,
            "latest": rows[0] if rows else None,
            "drift_events": list(reversed(drift_rows)),
        }

    def artifacts_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT path,sha256,size FROM run_artifacts WHERE run_id=? ORDER BY path",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_job(self, job_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
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
        with self._connection() as connection:
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
        with self._connection() as connection:
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
        with self._connection() as connection:
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
            with self._connection() as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                runs = int(connection.execute("SELECT COUNT(*) FROM validation_runs").fetchone()[0])
                artifacts = int(connection.execute("SELECT COUNT(*) FROM run_artifacts").fetchone()[0])
            return {
                "passed": integrity == "ok" and version == SCHEMA_VERSION,
                "integrity": integrity,
                "schema_version": version,
                "runs": runs,
                "artifacts": artifacts,
            }
        except sqlite3.Error:
            return {
                "passed": False,
                "error": "Database health check failed.",
                "schema_version": None,
                "runs": None,
                "artifacts": None,
            }
