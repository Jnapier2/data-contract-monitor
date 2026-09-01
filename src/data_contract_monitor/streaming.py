from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .limits import ResourceLimits
from .models import ColumnProfile, DatasetProfile
from .pii import detect_pii
from .profiler import infer_observed_type


def _scalar_key(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        normalized: Any = {"t": "datetime", "v": value.isoformat()}
    elif isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        normalized = {"t": "int", "v": int(value)}
    elif isinstance(value, (np.floating, float)):
        numeric = float(value)
        if math.isnan(numeric):
            return None
        normalized = {"t": "float", "v": repr(numeric)}
    elif isinstance(value, (np.bool_, bool)):
        normalized = {"t": "bool", "v": bool(value)}
    else:
        normalized = {"t": "str", "v": str(value)}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def composite_key(values: Iterable[Any]) -> str | None:
    items: list[str] = []
    any_value = False
    for value in values:
        key = _scalar_key(value)
        if key is None:
            items.append("NULL")
        else:
            any_value = True
            items.append(key)
    if not any_value:
        return None
    return hashlib.sha256("|".join(items).encode("ascii")).hexdigest()


class DiskKeyStore:
    """Disk-backed exact key counting that stores only SHA-256 key material."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=OFF")
        self.connection.execute("PRAGMA synchronous=OFF")
        self.connection.execute("PRAGMA temp_store=MEMORY")
        self.connection.execute("PRAGMA cache_size=-32768")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS key_counts(
                namespace TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                first_row INTEGER NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY(namespace,key_hash)
            ) WITHOUT ROWID
            """
        )
        self.connection.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS incoming_keys(
                namespace TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                first_row INTEGER NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY(namespace,key_hash)
            ) WITHOUT ROWID
            """
        )

    def close(self) -> None:
        self.connection.close()

    def _stage(self, namespace: str, grouped: dict[str, list[int]]) -> None:
        self.connection.execute("DELETE FROM incoming_keys")
        self.connection.executemany(
            "INSERT INTO incoming_keys(namespace,key_hash,first_row,count) VALUES(?,?,?,?)",
            [
                (namespace, key_hash, rows[0], len(rows))
                for key_hash, rows in grouped.items()
            ],
        )

    def add_grouped(
        self,
        namespace: str,
        grouped: dict[str, list[int]],
        *,
        sample_limit: int = 10,
    ) -> tuple[int, list[int]]:
        """Return newly affected duplicate rows and bounded example row numbers."""
        if not grouped:
            return 0, []
        self._stage(namespace, grouped)
        affected = int(
            self.connection.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                      WHEN k.key_hash IS NULL AND i.count > 1 THEN i.count
                      WHEN k.key_hash IS NOT NULL THEN i.count + CASE WHEN k.count=1 THEN 1 ELSE 0 END
                      ELSE 0
                    END
                ),0)
                FROM incoming_keys i
                LEFT JOIN key_counts k
                  ON k.namespace=i.namespace AND k.key_hash=i.key_hash
                """
            ).fetchone()[0]
        )
        samples: list[int] = []
        rows = self.connection.execute(
            """
            SELECT i.key_hash,k.first_row,k.count,i.count
            FROM incoming_keys i
            LEFT JOIN key_counts k
              ON k.namespace=i.namespace AND k.key_hash=i.key_hash
            WHERE (k.key_hash IS NOT NULL) OR i.count > 1
            ORDER BY COALESCE(k.first_row,i.first_row), i.first_row
            LIMIT ?
            """,
            (sample_limit,),
        ).fetchall()
        for key_hash, prior_first, prior_count, _incoming_count in rows:
            current_rows = grouped[str(key_hash)]
            if prior_first is not None and int(prior_count) == 1:
                samples.append(int(prior_first))
            samples.extend(current_rows[: max(0, sample_limit - len(samples))])
            if len(samples) >= sample_limit:
                break
        self.connection.execute(
            """
            INSERT INTO key_counts(namespace,key_hash,first_row,count)
            SELECT namespace,key_hash,first_row,count FROM incoming_keys WHERE 1
            ON CONFLICT(namespace,key_hash) DO UPDATE SET count=key_counts.count+excluded.count
            """
        )
        self.connection.commit()
        return affected, sorted(set(samples))[:sample_limit]

    def add_reference_keys(self, namespace: str, hashes: set[str]) -> None:
        if not hashes:
            return
        self.connection.executemany(
            "INSERT OR IGNORE INTO key_counts(namespace,key_hash,first_row,count) VALUES(?,?,0,1)",
            [(namespace, key_hash) for key_hash in hashes],
        )
        self.connection.commit()

    def missing_reference_keys(self, namespace: str, hashes: set[str]) -> set[str]:
        if not hashes:
            return set()
        grouped = {key_hash: [0] for key_hash in hashes}
        self._stage(namespace, grouped)
        rows = self.connection.execute(
            """
            SELECT i.key_hash
            FROM incoming_keys i
            LEFT JOIN key_counts k
              ON k.namespace=i.namespace AND k.key_hash=i.key_hash
            WHERE k.key_hash IS NULL
            """
        ).fetchall()
        return {str(row[0]) for row in rows}


@dataclass
class _ProfileColumnState:
    null_count: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    distinct_exact: bool = True
    type_samples: list[Any] = field(default_factory=list)
    numeric_possible: bool = True
    numeric_count: int = 0
    numeric_sum: float = 0.0
    numeric_min: float | None = None
    numeric_max: float | None = None


class StreamingProfiler:
    def __init__(self, columns: list[str], limits: ResourceLimits) -> None:
        self.columns = columns
        self.limits = limits
        self.row_count = 0
        self.states = {column: _ProfileColumnState() for column in columns}
        self._tracked_distinct = 0
        self._pii_frames: list[pd.DataFrame] = []
        self._pii_rows = 0

    def update(self, frame: pd.DataFrame) -> None:
        self.row_count += len(frame)
        remaining = self.limits.max_pii_sample_rows - self._pii_rows
        if remaining > 0 and len(frame):
            sample = frame.head(remaining).copy()
            self._pii_frames.append(sample)
            self._pii_rows += len(sample)
        for column in self.columns:
            if column not in frame.columns:
                continue
            series = frame[column]
            state = self.states[column]
            state.null_count += int(series.isna().sum())
            if len(state.type_samples) < 200:
                state.type_samples.extend(series.dropna().head(200 - len(state.type_samples)).tolist())
            numeric = pd.to_numeric(series, errors="coerce")
            non_null = series.notna()
            if int((non_null & numeric.isna()).sum()):
                state.numeric_possible = False
            valid_numeric = numeric.dropna()
            if len(valid_numeric):
                values = valid_numeric.astype(float)
                state.numeric_count += len(values)
                state.numeric_sum += float(values.sum())
                chunk_min = float(values.min())
                chunk_max = float(values.max())
                state.numeric_min = chunk_min if state.numeric_min is None else min(state.numeric_min, chunk_min)
                state.numeric_max = chunk_max if state.numeric_max is None else max(state.numeric_max, chunk_max)
            if state.distinct_exact:
                for value in series.dropna().tolist():
                    key = _scalar_key(value)
                    if key is None:
                        continue
                    if key not in state.counts:
                        if self._tracked_distinct >= self.limits.max_profile_distinct_track:
                            state.distinct_exact = False
                            break
                        self._tracked_distinct += 1
                        state.counts[key] = 1
                    else:
                        state.counts[key] += 1

    def finalize(self, *, include_pii: bool) -> DatasetProfile:
        profiles: list[ColumnProfile] = []
        bounded = False
        for column in self.columns:
            state = self.states[column]
            sample_series = pd.Series(state.type_samples, dtype="object")
            observed_type = infer_observed_type(sample_series)
            if state.numeric_possible and state.numeric_count and observed_type == "string":
                observed_type = "number"
            duplicate_count = sum(count for count in state.counts.values() if count > 1)
            minimum: float | str | None = None
            maximum: float | str | None = None
            mean: float | None = None
            if state.numeric_possible and state.numeric_count:
                minimum = state.numeric_min
                maximum = state.numeric_max
                mean = round(state.numeric_sum / state.numeric_count, 6)
            if not state.distinct_exact:
                bounded = True
            profiles.append(
                ColumnProfile(
                    name=column,
                    observed_type=observed_type,
                    null_count=state.null_count,
                    null_ratio=round(state.null_count / self.row_count, 6) if self.row_count else 0.0,
                    distinct_count=len(state.counts),
                    duplicate_count=duplicate_count,
                    distinct_count_exact=state.distinct_exact,
                    duplicate_count_exact=state.distinct_exact,
                    minimum=minimum,
                    maximum=maximum,
                    mean=mean,
                )
            )
        pii_frame = pd.concat(self._pii_frames, ignore_index=True) if self._pii_frames else pd.DataFrame(columns=self.columns)
        return DatasetProfile(
            row_count=self.row_count,
            column_count=len(self.columns),
            columns=profiles,
            pii_signals=detect_pii(pii_frame) if include_pii and len(pii_frame) else [],
            profiling_mode="bounded" if bounded or (include_pii and self.row_count > self._pii_rows) else "exact",
            sampled_rows=self._pii_rows if include_pii else 0,
        )
