from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import __version__
from .contract_loader import load_contract
from .contract_plan import compile_contract
from .drift import compare_profile, load_baseline
from .expression import evaluate_numeric_expression, referenced_names
from .history import append_history, default_history_path
from .io import read_dataset, sha256_file
from .limits import ResourceLimitError, ResourceLimits
from .models import (
    Contract,
    DatasetProfile,
    DatasetRule,
    DriftSummary,
    Finding,
    SEVERITY_ORDER,
    Severity,
    ValidationResult,
    ValidationSummary,
)
from .profiler import profile_dataset


class ValidationExecutionError(RuntimeError):
    """Raised for execution failures that are not data-quality findings."""


class ValidationCancelled(ValidationExecutionError):
    """Raised when a bounded validation job is cancelled cooperatively."""


def _checkpoint(
    stage: str,
    percent: int,
    *,
    started_monotonic: float,
    limits: ResourceLimits,
    progress: Callable[[str, int], None] | None,
    cancelled: Callable[[], bool] | None,
) -> None:
    if cancelled is not None and cancelled():
        raise ValidationCancelled(f"Validation cancelled during {stage}.")
    if monotonic() - started_monotonic > limits.max_runtime_seconds:
        raise ValidationExecutionError(
            f"Validation exceeded the {limits.max_runtime_seconds:g}-second execution budget."
        )
    if progress is not None:
        progress(stage, percent)


def _finding_id(rule_id: str, column: str | None, message: str) -> str:
    material = f"{rule_id}|{column or ''}|{message}".encode()
    return hashlib.sha256(material).hexdigest()[:16]


def _finding(
    *,
    rule_id: str,
    severity: Severity,
    category: str,
    title: str,
    message: str,
    column: str | None = None,
    affected_rows: int = 0,
    sample_rows: list[int] | None = None,
    expected: str | None = None,
    observed: str | None = None,
    remediation: str | None = None,
) -> Finding:
    return Finding(
        id=_finding_id(rule_id, column, message),
        rule_id=rule_id,
        severity=severity,
        category=category,
        title=title,
        message=message,
        column=column,
        affected_rows=affected_rows,
        sample_rows=sample_rows or [],
        expected=expected,
        observed=observed,
        remediation=remediation,
    )


def _sample_rows(mask: pd.Series, limit: int = 10) -> list[int]:
    normalized = mask.fillna(False).to_numpy(dtype=bool)
    return [int(position) + 1 for position in np.flatnonzero(normalized)[:limit]]


def _parse_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _parse_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")


def _invalid_type_mask(series: pd.Series, expected: str, strict: bool) -> pd.Series:
    non_null = series.notna()
    invalid = pd.Series(False, index=series.index)
    if expected == "any":
        return invalid
    if expected == "string":
        if strict:
            invalid.loc[non_null] = ~series.loc[non_null].map(lambda value: isinstance(value, str))
        return invalid
    if expected in {"integer", "number"}:
        numeric = _parse_numeric(series)
        invalid = non_null & numeric.isna()
        if expected == "integer":
            valid_numeric = numeric.notna()
            invalid = invalid | (valid_numeric & ((numeric % 1).abs() > 1e-12))
        return invalid
    if expected == "boolean":
        accepted = {True, False, 0, 1, "0", "1", "true", "false", "yes", "no", "y", "n"}
        invalid.loc[non_null] = ~series.loc[non_null].map(
            lambda value: value if isinstance(value, bool) else str(value).strip().lower()
        ).isin(accepted)
        return invalid
    if expected in {"date", "datetime"}:
        parsed = _parse_datetime(series)
        return non_null & parsed.isna()
    if expected == "email":
        pattern = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
        invalid.loc[non_null] = ~series.loc[non_null].astype(str).str.fullmatch(pattern)
        return invalid
    if expected == "uuid":
        def is_uuid(value: Any) -> bool:
            try:
                uuid.UUID(str(value))
                return True
            except (ValueError, AttributeError, TypeError):
                return False
        invalid.loc[non_null] = ~series.loc[non_null].map(is_uuid)
        return invalid
    return invalid


def _validate_columns(frame: pd.DataFrame, contract: Contract) -> list[Finding]:
    findings: list[Finding] = []
    actual_columns = set(frame.columns)
    required_columns = set(contract.dataset.required_columns)
    for column in sorted(required_columns - actual_columns):
        findings.append(
            _finding(
                rule_id="schema.required_column",
                severity=Severity.CRITICAL,
                category="schema",
                title="Required column is missing",
                message=f"Required column '{column}' is not present in the dataset.",
                column=column,
                expected="column present",
                observed="column absent",
                remediation="Add the column or revise the contract through review and version control.",
            )
        )
    if not contract.dataset.allow_extra_columns:
        for column in sorted(actual_columns - required_columns):
            findings.append(
                _finding(
                    rule_id="schema.extra_column",
                    severity=contract.dataset.extra_columns_severity,
                    category="schema",
                    title="Unexpected column is present",
                    message=f"Column '{column}' is not declared by the contract.",
                    column=column,
                    expected="declared contract column",
                    observed="undeclared column",
                    remediation="Remove the column or approve it in a new contract version.",
                )
            )

    for column, rule in contract.rules.items():
        if column not in frame.columns:
            continue
        series = frame[column]
        if not rule.nullable:
            mask = series.isna()
            count = int(mask.sum())
            if count:
                findings.append(
                    _finding(
                        rule_id="column.nullable",
                        severity=rule.severity,
                        category="completeness",
                        title="Null values are not allowed",
                        message=f"Column '{column}' contains {count} null value(s).",
                        column=column,
                        affected_rows=count,
                        sample_rows=_sample_rows(mask),
                        expected="0 null values",
                        observed=f"{count} null values",
                        remediation="Populate the missing values upstream or explicitly revise nullability.",
                    )
                )
        invalid_type = _invalid_type_mask(series, rule.data_type, rule.strict_type)
        invalid_count = int(invalid_type.sum())
        if invalid_count:
            findings.append(
                _finding(
                    rule_id="column.type",
                    severity=rule.severity,
                    category="validity",
                    title="Values do not match the expected type",
                    message=f"Column '{column}' has {invalid_count} value(s) incompatible with type '{rule.data_type}'.",
                    column=column,
                    affected_rows=invalid_count,
                    sample_rows=_sample_rows(invalid_type),
                    expected=rule.data_type,
                    observed=f"{invalid_count} incompatible values",
                    remediation="Correct the source values or revise the logical type deliberately.",
                )
            )
        if rule.unique:
            duplicate_mask = series.notna() & series.duplicated(keep=False)
            duplicate_count = int(duplicate_mask.sum())
            if duplicate_count:
                findings.append(
                    _finding(
                        rule_id="column.unique",
                        severity=rule.severity,
                        category="uniqueness",
                        title="Duplicate values violate uniqueness",
                        message=f"Column '{column}' contains {duplicate_count} row(s) participating in duplicates.",
                        column=column,
                        affected_rows=duplicate_count,
                        sample_rows=_sample_rows(duplicate_mask),
                        expected="unique non-null values",
                        observed=f"{duplicate_count} duplicate rows",
                        remediation="Deduplicate at the source and confirm the intended business key.",
                    )
                )
        if rule.minimum is not None or rule.maximum is not None:
            numeric = _parse_numeric(series)
            if rule.minimum is not None:
                mask = numeric.notna() & (numeric < rule.minimum)
                count = int(mask.sum())
                if count:
                    findings.append(
                        _finding(
                            rule_id="column.minimum",
                            severity=rule.severity,
                            category="validity",
                            title="Values fall below the permitted minimum",
                            message=f"Column '{column}' has {count} value(s) below {rule.minimum}.",
                            column=column,
                            affected_rows=count,
                            sample_rows=_sample_rows(mask),
                            expected=f">= {rule.minimum}",
                            observed=f"{count} values below minimum",
                            remediation="Correct negative or out-of-range values upstream.",
                        )
                    )
            if rule.maximum is not None:
                mask = numeric.notna() & (numeric > rule.maximum)
                count = int(mask.sum())
                if count:
                    findings.append(
                        _finding(
                            rule_id="column.maximum",
                            severity=rule.severity,
                            category="validity",
                            title="Values exceed the permitted maximum",
                            message=f"Column '{column}' has {count} value(s) above {rule.maximum}.",
                            column=column,
                            affected_rows=count,
                            sample_rows=_sample_rows(mask),
                            expected=f"<= {rule.maximum}",
                            observed=f"{count} values above maximum",
                            remediation="Correct out-of-range values upstream or revise the boundary with approval.",
                        )
                    )
        if rule.min_length is not None or rule.max_length is not None:
            lengths = series.dropna().astype(str).str.len().reindex(series.index)
            if rule.min_length is not None:
                mask = series.notna() & (lengths < rule.min_length)
                count = int(mask.sum())
                if count:
                    findings.append(
                        _finding(
                            rule_id="column.min_length",
                            severity=rule.severity,
                            category="validity",
                            title="Text values are too short",
                            message=f"Column '{column}' has {count} value(s) shorter than {rule.min_length} characters.",
                            column=column,
                            affected_rows=count,
                            sample_rows=_sample_rows(mask),
                        )
                    )
            if rule.max_length is not None:
                mask = series.notna() & (lengths > rule.max_length)
                count = int(mask.sum())
                if count:
                    findings.append(
                        _finding(
                            rule_id="column.max_length",
                            severity=rule.severity,
                            category="validity",
                            title="Text values are too long",
                            message=f"Column '{column}' has {count} value(s) longer than {rule.max_length} characters.",
                            column=column,
                            affected_rows=count,
                            sample_rows=_sample_rows(mask),
                        )
                    )
        if rule.pattern:
            try:
                pattern = re.compile(rule.pattern)
            except re.error as exc:
                raise ValidationExecutionError(f"Invalid regex for column '{column}': {exc}") from exc
            mask = series.notna() & ~series.astype(str).str.fullmatch(pattern)
            count = int(mask.sum())
            if count:
                findings.append(
                    _finding(
                        rule_id="column.pattern",
                        severity=rule.severity,
                        category="validity",
                        title="Values do not match the required pattern",
                        message=f"Column '{column}' has {count} value(s) that do not match the configured pattern.",
                        column=column,
                        affected_rows=count,
                        sample_rows=_sample_rows(mask),
                        expected="configured regular expression",
                        observed=f"{count} non-matching values",
                    )
                )
        if rule.allowed_values is not None:
            mask = series.notna() & ~series.isin(rule.allowed_values)
            count = int(mask.sum())
            if count:
                findings.append(
                    _finding(
                        rule_id="column.allowed_values",
                        severity=rule.severity,
                        category="validity",
                        title="Values fall outside the approved set",
                        message=f"Column '{column}' has {count} unapproved value(s).",
                        column=column,
                        affected_rows=count,
                        sample_rows=_sample_rows(mask),
                        expected=f"one of {len(rule.allowed_values)} approved values",
                        observed=f"{count} unapproved values",
                        remediation="Correct the values or approve a contract change.",
                    )
                )
        if rule.maximum_age_hours is not None:
            parsed = _parse_datetime(series)
            cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=rule.maximum_age_hours)
            mask = parsed.notna() & (parsed < cutoff)
            count = int(mask.sum())
            if count:
                findings.append(
                    _finding(
                        rule_id="column.maximum_age_hours",
                        severity=rule.severity,
                        category="freshness",
                        title="Data is older than the freshness requirement",
                        message=f"Column '{column}' has {count} timestamp(s) older than {rule.maximum_age_hours} hour(s).",
                        column=column,
                        affected_rows=count,
                        sample_rows=_sample_rows(mask),
                        expected=f"age <= {rule.maximum_age_hours} hours",
                        observed=f"{count} stale rows",
                        remediation="Restore the upstream refresh or approve a temporary freshness exception.",
                    )
                )
    return findings


def _validate_dataset_rules(frame: pd.DataFrame, rules: list[DatasetRule]) -> list[Finding]:
    findings: list[Finding] = []
    for index, rule in enumerate(rules, start=1):
        rule_name = rule.name or f"dataset_rule_{index}"
        if rule.type == "row_count":
            count = len(frame)
            violation = (rule.minimum is not None and count < rule.minimum) or (
                rule.maximum is not None and count > rule.maximum
            )
            if violation:
                expected = f"{rule.minimum if rule.minimum is not None else '-∞'} to {rule.maximum if rule.maximum is not None else '∞'} rows"
                findings.append(
                    _finding(
                        rule_id=f"dataset.row_count.{rule_name}",
                        severity=rule.severity,
                        category="volume",
                        title="Dataset row count is outside the expected range",
                        message=f"Dataset contains {count} row(s), outside the configured range.",
                        expected=expected,
                        observed=f"{count} rows",
                        remediation="Investigate upstream completeness, duplication, or filtering changes.",
                    )
                )
        elif rule.type == "unique_combination":
            columns = rule.columns or []
            missing = [column for column in columns if column not in frame.columns]
            if missing:
                continue
            mask = frame.duplicated(subset=columns, keep=False)
            count = int(mask.sum())
            if count:
                findings.append(
                    _finding(
                        rule_id=f"dataset.unique_combination.{rule_name}",
                        severity=rule.severity,
                        category="uniqueness",
                        title="Composite key is not unique",
                        message=f"{count} row(s) duplicate the configured combination of {len(columns)} columns.",
                        affected_rows=count,
                        sample_rows=_sample_rows(mask),
                        expected="unique column combination",
                        observed=f"{count} duplicate rows",
                        remediation="Resolve duplicate business keys at the source.",
                    )
                )
        elif rule.type == "null_ratio":
            if not rule.column or rule.column not in frame.columns or rule.max_ratio is None:
                continue
            ratio = float(frame[rule.column].isna().mean()) if len(frame) else 0.0
            if ratio > rule.max_ratio:
                count = int(frame[rule.column].isna().sum())
                findings.append(
                    _finding(
                        rule_id=f"dataset.null_ratio.{rule_name}",
                        severity=rule.severity,
                        category="completeness",
                        title="Null ratio exceeds the permitted threshold",
                        message=f"Column '{rule.column}' is {ratio:.2%} null, above the {rule.max_ratio:.2%} limit.",
                        column=rule.column,
                        affected_rows=count,
                        sample_rows=_sample_rows(frame[rule.column].isna()),
                        expected=f"null ratio <= {rule.max_ratio:.2%}",
                        observed=f"null ratio {ratio:.2%}",
                    )
                )
        elif rule.type == "conditional_not_null":
            if not rule.when_column or not rule.then_column:
                continue
            if rule.when_column not in frame.columns or rule.then_column not in frame.columns:
                continue
            mask = (frame[rule.when_column] == rule.when_equals) & frame[rule.then_column].isna()
            count = int(mask.sum())
            if count:
                findings.append(
                    _finding(
                        rule_id=f"dataset.conditional_not_null.{rule_name}",
                        severity=rule.severity,
                        category="completeness",
                        title="Conditionally required values are missing",
                        message=f"{count} row(s) require '{rule.then_column}' when '{rule.when_column}' matches the configured condition.",
                        column=rule.then_column,
                        affected_rows=count,
                        sample_rows=_sample_rows(mask),
                    )
                )
        elif rule.type == "aggregate_reconciliation":
            if not rule.left_column or not rule.right_expression:
                continue
            expression_columns = referenced_names(rule.right_expression)
            required = {rule.left_column, *expression_columns}
            if not required.issubset(frame.columns):
                continue
            left = pd.to_numeric(frame[rule.left_column], errors="coerce")
            right = evaluate_numeric_expression(
                rule.right_expression,
                {name: frame[name] for name in expression_columns},
            )
            comparable = left.notna() & right.notna() & np.isfinite(left) & np.isfinite(right)
            mask = comparable & ((left - right).abs() > rule.tolerance)
            count = int(mask.sum())
            if count:
                findings.append(
                    _finding(
                        rule_id=f"dataset.aggregate_reconciliation.{rule_name}",
                        severity=rule.severity,
                        category="reconciliation",
                        title="Aggregate reconciliation does not balance",
                        message=(
                            f"{count} row(s) differ between '{rule.left_column}' and the approved "
                            f"expression by more than tolerance {rule.tolerance}."
                        ),
                        column=rule.left_column,
                        affected_rows=count,
                        sample_rows=_sample_rows(mask),
                        expected=f"abs({rule.left_column} - ({rule.right_expression})) <= {rule.tolerance}",
                        observed=f"{count} rows outside tolerance",
                        remediation="Correct component values or approve a contract change to the reconciliation formula.",
                    )
                )
    return findings


def _privacy_findings(contract: Contract, profile: DatasetProfile) -> list[Finding]:
    if not contract.privacy.detect_pii:
        return []
    allowed = set(contract.privacy.allowed_categories)
    findings: list[Finding] = []
    for signal in profile.pii_signals:
        if signal.category in allowed:
            continue
        severity = Severity.ERROR if contract.privacy.fail_on_unapproved else contract.privacy.severity
        findings.append(
            _finding(
                rule_id="privacy.unapproved_pii_signal",
                severity=severity,
                category="privacy",
                title="Potential sensitive field is not approved by the contract",
                message=f"Column '{signal.column}' has a {signal.confidence}-confidence '{signal.category}' signal.",
                column=signal.column,
                expected="approved privacy category or reviewed false positive",
                observed=f"{signal.confidence}-confidence {signal.category} signal",
                remediation="Review classification; allow the category explicitly or remove/mask the field.",
            )
        )
    return findings


def _drift_findings(drift: DriftSummary) -> list[Finding]:
    findings: list[Finding] = []
    for change in drift.changes:
        findings.append(
            _finding(
                rule_id=f"drift.{change.change_type}",
                severity=change.severity,
                category="drift",
                title=f"Schema drift: {change.change_type.replace('_', ' ')}",
                message=f"Column '{change.column}' changed relative to the approved baseline.",
                column=change.column,
                expected=str(change.before) if change.before is not None else None,
                observed=str(change.after) if change.after is not None else None,
                remediation="Review the change, update downstream consumers, and approve a new baseline if intentional.",
            )
        )
    return findings


def _summary(findings: list[Finding], fail_on: Severity) -> ValidationSummary:
    counts = {severity: 0 for severity in Severity}
    for finding in findings:
        counts[finding.severity] += 1
    passed = not any(SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER[fail_on] for finding in findings)
    return ValidationSummary(
        status="passed" if passed else "failed",
        passed=passed,
        fail_on=fail_on,
        findings_total=len(findings),
        info=counts[Severity.INFO],
        warnings=counts[Severity.WARNING],
        errors=counts[Severity.ERROR],
        critical=counts[Severity.CRITICAL],
    )


def validate_files(
    *,
    contract_path: Path,
    data_path: Path,
    baseline_path: Path | None = None,
    fail_on: Severity = Severity.ERROR,
    object_name: str | None = None,
    sheet_name: str | int = 0,
    record_history: bool = True,
    history_path: Path | None = None,
    limits: ResourceLimits | None = None,
    progress: Callable[[str, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ValidationResult:
    started = datetime.now(UTC)
    started_monotonic = monotonic()
    run_id = uuid.uuid4().hex
    effective_limits = limits or ResourceLimits()
    try:
        effective_limits.check_file_sizes(contract_path, data_path)
    except (OSError, ResourceLimitError) as exc:
        raise ValidationExecutionError(str(exc)) from exc

    _checkpoint(
        "loading_contract", 10, started_monotonic=started_monotonic, limits=effective_limits,
        progress=progress, cancelled=cancelled,
    )
    contract = load_contract(contract_path, object_name=object_name)
    plan = compile_contract(contract)

    _checkpoint(
        "reading_dataset", 25, started_monotonic=started_monotonic, limits=effective_limits,
        progress=progress, cancelled=cancelled,
    )
    frame = read_dataset(data_path, sheet_name=sheet_name)
    try:
        effective_limits.check_shape(len(frame), len(frame.columns))
    except ResourceLimitError as exc:
        raise ValidationExecutionError(str(exc)) from exc

    _checkpoint(
        "profiling", 45, started_monotonic=started_monotonic, limits=effective_limits,
        progress=progress, cancelled=cancelled,
    )
    profile = profile_dataset(frame, include_pii=plan.contract.privacy.detect_pii)
    drift = DriftSummary()
    if baseline_path:
        drift = compare_profile(profile, load_baseline(baseline_path), baseline_path)

    _checkpoint(
        "validating", 65, started_monotonic=started_monotonic, limits=effective_limits,
        progress=progress, cancelled=cancelled,
    )
    findings = [
        *_validate_columns(frame, plan.contract),
        *_validate_dataset_rules(frame, plan.contract.dataset_rules),
        *_privacy_findings(plan.contract, profile),
        *_drift_findings(drift),
    ]
    findings.sort(key=lambda item: (-SEVERITY_ORDER[item.severity], item.category, item.rule_id, item.column or ""))
    findings_truncated = False
    completeness = "complete"
    if len(findings) > effective_limits.max_findings:
        findings_truncated = True
        completeness = "partial"
        original_count = len(findings)
        findings = findings[: max(0, effective_limits.max_findings - 1)]
        findings.append(
            _finding(
                rule_id="runtime.finding_limit",
                severity=Severity.CRITICAL,
                category="runtime",
                title="Finding evidence limit reached",
                message=(
                    f"Validation produced {original_count} findings; evidence was capped at "
                    f"{effective_limits.max_findings}. The result is partial."
                ),
                expected=f"<= {effective_limits.max_findings} findings",
                observed=f"{original_count} findings",
            )
        )

    _checkpoint(
        "finalizing", 80, started_monotonic=started_monotonic, limits=effective_limits,
        progress=progress, cancelled=cancelled,
    )
    completed = datetime.now(UTC)
    result = ValidationResult(
        tool_version=__version__,
        run_id=run_id,
        dataset_name=plan.contract.dataset.name,
        contract_label=contract_path.name,
        data_label=data_path.name,
        started_at=started,
        completed_at=completed,
        duration_ms=max(0, int((completed - started).total_seconds() * 1000)),
        contract_sha256=sha256_file(contract_path),
        data_sha256=sha256_file(data_path),
        source_format=plan.contract.source_format,
        source_standard_version=plan.contract.source_standard_version,
        summary=_summary(findings, fail_on),
        findings=findings,
        profile=profile,
        drift=drift,
        completeness=completeness,
        findings_truncated=findings_truncated,
        limits_applied=effective_limits.public_dict(),
    )
    if record_history:
        append_history(history_path or default_history_path(contract_path), result)
    _checkpoint(
        "completed", 85, started_monotonic=started_monotonic, limits=effective_limits,
        progress=progress, cancelled=cancelled,
    )
    return result
