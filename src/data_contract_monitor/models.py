from __future__ import annotations

from datetime import datetime
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 10,
    Severity.WARNING: 20,
    Severity.ERROR: 30,
    Severity.CRITICAL: 40,
}


class DatasetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    owner: str | None = None
    required_columns: list[str] = Field(default_factory=list)
    allow_extra_columns: bool = True
    extra_columns_severity: Severity = Severity.WARNING


class ColumnRule(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    data_type: Literal[
        "any", "string", "integer", "number", "boolean", "date", "datetime", "email", "uuid"
    ] = Field(default="any", alias="type")
    nullable: bool = True
    unique: bool = False
    strict_type: bool = False
    minimum: float | None = None
    maximum: float | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    pattern: str | None = None
    allowed_values: list[Any] | None = None
    maximum_age_hours: float | None = Field(default=None, gt=0)
    severity: Severity = Severity.ERROR
    description: str | None = None
    classification: str | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> ColumnRule:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot be greater than maximum")
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise ValueError("min_length cannot be greater than max_length")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regular-expression pattern: {exc}") from exc
        return self


class DatasetRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    type: Literal["row_count", "unique_combination", "null_ratio", "conditional_not_null"]
    severity: Severity = Severity.ERROR
    description: str | None = None
    columns: list[str] | None = None
    column: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    max_ratio: float | None = Field(default=None, ge=0, le=1)
    when_column: str | None = None
    when_equals: Any | None = None
    then_column: str | None = None

    @model_validator(mode="after")
    def validate_rule_shape(self) -> DatasetRule:
        if self.type == "row_count" and self.minimum is None and self.maximum is None:
            raise ValueError("row_count requires minimum and/or maximum")
        if self.type == "unique_combination" and not self.columns:
            raise ValueError("unique_combination requires columns")
        if self.type == "null_ratio" and (not self.column or self.max_ratio is None):
            raise ValueError("null_ratio requires column and max_ratio")
        if self.type == "conditional_not_null" and (
            not self.when_column or self.then_column is None
        ):
            raise ValueError(
                "conditional_not_null requires when_column, when_equals, and then_column"
            )
        return self


class PrivacySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detect_pii: bool = True
    allowed_categories: list[str] = Field(default_factory=list)
    fail_on_unapproved: bool = False
    severity: Severity = Severity.WARNING


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = "1.0"
    dataset: DatasetSpec
    rules: dict[str, ColumnRule] = Field(default_factory=dict)
    dataset_rules: list[DatasetRule] = Field(default_factory=list)
    privacy: PrivacySpec = Field(default_factory=PrivacySpec)
    source_format: Literal["native", "odcs"] = "native"
    source_standard_version: str | None = None
    adapter_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_required_columns(self) -> Contract:
        seen: set[str] = set()
        normalized: list[str] = []
        for name in [*self.dataset.required_columns, *self.rules.keys()]:
            if name not in seen:
                seen.add(name)
                normalized.append(name)
        self.dataset.required_columns = normalized
        return self


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    rule_id: str
    severity: Severity
    category: str
    title: str
    message: str
    column: str | None = None
    affected_rows: int = 0
    sample_rows: list[int] = Field(default_factory=list)
    expected: str | None = None
    observed: str | None = None
    remediation: str | None = None


class PiiSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    category: str
    confidence: Literal["low", "medium", "high"]
    name_signal: bool
    sampled_values: int = 0
    matching_values: int = 0
    match_ratio: float = 0


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    observed_type: str
    null_count: int
    null_ratio: float
    distinct_count: int
    duplicate_count: int
    minimum: float | str | None = None
    maximum: float | str | None = None
    mean: float | None = None


class DatasetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    pii_signals: list[PiiSignal] = Field(default_factory=list)


class DriftChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_type: Literal["added", "removed", "type_changed", "nullability_changed"]
    column: str
    before: str | bool | None = None
    after: str | bool | None = None
    severity: Severity


class DriftSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_used: bool = False
    baseline_path: str | None = None
    changes: list[DriftChange] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["passed", "failed"]
    passed: bool
    fail_on: Severity
    findings_total: int
    info: int
    warnings: int
    errors: int
    critical: int


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    tool_version: str
    run_id: str
    dataset_name: str
    contract_label: str
    data_label: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    contract_sha256: str
    data_sha256: str
    source_format: str
    source_standard_version: str | None = None
    summary: ValidationSummary
    findings: list[Finding]
    profile: DatasetProfile
    drift: DriftSummary
    privacy_note: str = (
        "Reports contain aggregate statistics and row numbers, not raw cell values."
    )
