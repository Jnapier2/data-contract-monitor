from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import ColumnRule, Contract, DatasetRule, DatasetSpec, PrivacySpec, Severity


class ContractLoadError(ValueError):
    """Raised when a contract cannot be parsed or validated."""


def _severity(value: Any, default: Severity = Severity.ERROR) -> Severity:
    try:
        return Severity(str(value).lower())
    except ValueError:
        return default


def _logical_type(value: Any) -> str:
    normalized = str(value or "any").lower().strip()
    mapping = {
        "varchar": "string",
        "char": "string",
        "text": "string",
        "string": "string",
        "int": "integer",
        "integer": "integer",
        "long": "integer",
        "bigint": "integer",
        "smallint": "integer",
        "float": "number",
        "double": "number",
        "decimal": "number",
        "numeric": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
        "date": "date",
        "timestamp": "datetime",
        "datetime": "datetime",
        "uuid": "uuid",
        "email": "email",
    }
    for key, target in mapping.items():
        if normalized == key or normalized.startswith(f"{key}("):
            return target
    return "any"


def _choose_odcs_object(payload: dict[str, Any], object_name: str | None) -> dict[str, Any]:
    schema = payload.get("schema")
    if not isinstance(schema, list) or not schema:
        raise ContractLoadError("ODCS contract does not contain a non-empty schema list")
    if object_name:
        for item in schema:
            candidates = {item.get("name"), item.get("physicalName"), item.get("businessName")}
            if object_name in candidates:
                return item
        raise ContractLoadError(f"ODCS schema object not found: {object_name}")
    return schema[0]


def _adapt_odcs(payload: dict[str, Any], object_name: str | None) -> Contract:
    obj = _choose_odcs_object(payload, object_name)
    properties = obj.get("properties") or []
    if not isinstance(properties, list):
        raise ContractLoadError("ODCS schema object's properties must be a list")

    rules: dict[str, ColumnRule] = {}
    required_columns: list[str] = []
    notes = [
        "ODCS adapter validates one schema object per run.",
        "Supported ODCS fields: property name/physicalName, logicalType/physicalType, required, unique, classification, selected nullValues quality checks, and rowCount quality checks.",
        "Unmapped ODCS metadata remains documentary and is not silently enforced.",
    ]

    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = str(prop.get("physicalName") or prop.get("name") or "").strip()
        if not name:
            continue
        required_columns.append(name)
        nullable = not bool(prop.get("required", False))
        unique = bool(prop.get("unique", False) or prop.get("primaryKey", False))
        severity = Severity.ERROR
        for quality in prop.get("quality") or []:
            if not isinstance(quality, dict):
                continue
            if quality.get("metric") == "nullValues" and quality.get("mustBe") == 0:
                nullable = False
                severity = _severity(quality.get("severity"), severity)
            if quality.get("metric") in {"duplicateValues", "duplicates"} and quality.get("mustBe") == 0:
                unique = True
                severity = _severity(quality.get("severity"), severity)
        rules[name] = ColumnRule(
            type=_logical_type(prop.get("logicalType") or prop.get("physicalType")),
            nullable=nullable,
            unique=unique,
            severity=severity,
            description=prop.get("description"),
            classification=prop.get("classification"),
        )

    dataset_rules: list[DatasetRule] = []
    for quality in obj.get("quality") or []:
        if not isinstance(quality, dict) or quality.get("metric") != "rowCount":
            continue
        minimum: float | None = None
        maximum: float | None = None
        if "mustBe" in quality:
            minimum = maximum = float(quality["mustBe"])
        if "mustBeGreaterThan" in quality:
            minimum = float(quality["mustBeGreaterThan"]) + 1
        if "mustBeGreaterOrEqualTo" in quality:
            minimum = float(quality["mustBeGreaterOrEqualTo"])
        if "mustBeLessThan" in quality:
            maximum = float(quality["mustBeLessThan"]) - 1
        if "mustBeLessOrEqualTo" in quality:
            maximum = float(quality["mustBeLessOrEqualTo"])
        if minimum is not None or maximum is not None:
            dataset_rules.append(
                DatasetRule(
                    name="odcs_row_count",
                    type="row_count",
                    minimum=minimum,
                    maximum=maximum,
                    severity=_severity(quality.get("severity")),
                    description=quality.get("description"),
                )
            )

    owner: str | None = None
    team = payload.get("team") or {}
    for member in team.get("members") or []:
        if str(member.get("role", "")).lower() == "owner":
            owner = member.get("username")
            break
    owner = owner or team.get("name")

    name = str(obj.get("physicalName") or obj.get("name") or payload.get("dataProduct") or "dataset")
    return Contract(
        contract_version="1.0",
        dataset=DatasetSpec(
            name=name,
            description=obj.get("description"),
            owner=owner,
            required_columns=required_columns,
            allow_extra_columns=True,
        ),
        rules=rules,
        dataset_rules=dataset_rules,
        privacy=PrivacySpec(),
        source_format="odcs",
        source_standard_version=str(payload.get("apiVersion") or "unknown"),
        adapter_notes=notes,
    )


def load_contract(path: Path, *, object_name: str | None = None) -> Contract:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ContractLoadError(f"Unable to read YAML contract: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractLoadError("Contract root must be a YAML mapping")
    try:
        if payload.get("kind") == "DataContract" or str(payload.get("apiVersion", "")).startswith("v3"):
            return _adapt_odcs(payload, object_name)
        return Contract.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as exc:
        raise ContractLoadError(str(exc)) from exc
