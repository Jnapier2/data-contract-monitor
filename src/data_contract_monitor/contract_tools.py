from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml

from .contract_loader import ContractLoadError, load_contract
from .contract_plan import ContractPlanError, compile_contract
from .limits import ResourceLimitError, ResourceLimits
from .models import Contract
from .release_identity import find_root

ChangeClass = Literal[
    "breaking", "potentially_breaking", "nonbreaking", "documentation_only"
]
_CLASS_ORDER: dict[ChangeClass, int] = {
    "documentation_only": 10,
    "nonbreaking": 20,
    "potentially_breaking": 30,
    "breaking": 40,
}


def canonical_contract_payload(contract: Contract) -> dict[str, Any]:
    return contract.model_dump(mode="json", by_alias=True, exclude_none=True)


def normalized_contract_text(contract: Contract) -> str:
    return yaml.safe_dump(
        canonical_contract_payload(contract),
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
    )


def lint_contract(path: Path, *, limits: ResourceLimits | None = None) -> dict[str, Any]:
    effective = limits or ResourceLimits()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if path.stat().st_size > effective.max_contract_bytes:
            raise ResourceLimitError(
                f"Contract is {path.stat().st_size} bytes; limit is {effective.max_contract_bytes} bytes."
            )
        contract = load_contract(path)
        plan = compile_contract(contract)
        for column, rule in contract.rules.items():
            if rule.pattern:
                effective.check_regex(rule.pattern)
            if len(column) > effective.max_header_length:
                errors.append(
                    f"Column name '{column[:80]}' exceeds the {effective.max_header_length}-character header limit."
                )
        for rule in contract.dataset_rules:
            if rule.type == "reference_exists" and rule.reference_dataset:
                ref = Path(rule.reference_dataset)
                if ref.is_absolute():
                    errors.append(
                        f"reference_dataset '{rule.reference_dataset}' must be a relative path."
                    )
                else:
                    resolved = (path.parent / ref).resolve()
                    project_root = find_root(path.resolve())
                    allowed_root = project_root.resolve() if project_root is not None else path.parent.resolve()
                    if resolved != allowed_root and allowed_root not in resolved.parents:
                        errors.append(
                            f"reference_dataset '{rule.reference_dataset}' escapes the allowed project/contract directory."
                        )
                    elif not resolved.is_file():
                        warnings.append(
                            f"Reference dataset '{rule.reference_dataset}' is not currently present; validation will require it at runtime."
                        )
        if not contract.dataset.owner:
            warnings.append("Dataset owner is not declared.")
        if not contract.dataset.contract_id:
            warnings.append("dataset.contract_id is not declared; stable lifecycle identity is recommended.")
        if not contract.dataset.description:
            warnings.append("Dataset description is not declared.")
        if not contract.dataset.required_columns:
            warnings.append("No required columns are declared.")
        return {
            "passed": not errors,
            "errors": errors,
            "warnings": warnings,
            "dataset_name": contract.dataset.name,
            "contract_id": contract.dataset.contract_id,
            "contract_version": contract.contract_version,
            "source_format": contract.source_format,
            "rule_count": len(plan.rule_ids),
            "referenced_columns": list(plan.referenced_columns),
        }
    except (OSError, ContractLoadError, ContractPlanError, ResourceLimitError, ValueError) as exc:
        errors.append(str(exc))
        return {"passed": False, "errors": errors, "warnings": warnings}


def _change(path: str, classification: ChangeClass, before: Any, after: Any, reason: str) -> dict[str, Any]:
    return {
        "path": path,
        "classification": classification,
        "before": before,
        "after": after,
        "reason": reason,
    }


def diff_contracts(older: Contract, newer: Contract) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    if older.dataset.name != newer.dataset.name:
        changes.append(_change("dataset.name", "breaking", older.dataset.name, newer.dataset.name, "Dataset identity changed."))
    if older.dataset.contract_id != newer.dataset.contract_id:
        changes.append(_change("dataset.contract_id", "potentially_breaking", older.dataset.contract_id, newer.dataset.contract_id, "Stable lifecycle identity changed."))
    for field in ("description", "owner"):
        before = getattr(older.dataset, field)
        after = getattr(newer.dataset, field)
        if before != after:
            changes.append(_change(f"dataset.{field}", "documentation_only", before, after, "Documentary metadata changed."))

    old_required = set(older.dataset.required_columns)
    new_required = set(newer.dataset.required_columns)
    for column in sorted(new_required - old_required):
        changes.append(_change(f"dataset.required_columns.{column}", "breaking", False, True, "A new required column can reject previously valid datasets."))
    for column in sorted(old_required - new_required):
        changes.append(_change(f"dataset.required_columns.{column}", "nonbreaking", True, False, "A required-column constraint was relaxed."))

    all_columns = sorted(set(older.rules) | set(newer.rules))
    for column in all_columns:
        old = older.rules.get(column)
        new = newer.rules.get(column)
        if old is None and new is not None:
            classification: ChangeClass = "breaking" if column in new_required else "potentially_breaking"
            changes.append(_change(f"rules.{column}", classification, None, new.model_dump(mode="json", by_alias=True), "A new column rule was introduced."))
            continue
        if old is not None and new is None:
            changes.append(_change(f"rules.{column}", "nonbreaking", old.model_dump(mode="json", by_alias=True), None, "Column constraints were removed."))
            continue
        assert old is not None and new is not None
        if old.data_type != new.data_type:
            changes.append(_change(f"rules.{column}.type", "breaking", old.data_type, new.data_type, "Logical type changed."))
        if old.nullable and not new.nullable:
            changes.append(_change(f"rules.{column}.nullable", "breaking", True, False, "Nullability was tightened."))
        elif not old.nullable and new.nullable:
            changes.append(_change(f"rules.{column}.nullable", "nonbreaking", False, True, "Nullability was relaxed."))
        if not old.unique and new.unique:
            changes.append(_change(f"rules.{column}.unique", "breaking", False, True, "Uniqueness was newly required."))
        elif old.unique and not new.unique:
            changes.append(_change(f"rules.{column}.unique", "nonbreaking", True, False, "Uniqueness was relaxed."))
        if old.minimum != new.minimum:
            cls: ChangeClass = "breaking" if new.minimum is not None and (old.minimum is None or new.minimum > old.minimum) else "nonbreaking"
            changes.append(_change(f"rules.{column}.minimum", cls, old.minimum, new.minimum, "Minimum bound changed."))
        if old.maximum != new.maximum:
            cls = "breaking" if new.maximum is not None and (old.maximum is None or new.maximum < old.maximum) else "nonbreaking"
            changes.append(_change(f"rules.{column}.maximum", cls, old.maximum, new.maximum, "Maximum bound changed."))
        old_allowed = set(map(json.dumps, old.allowed_values or [])) if old.allowed_values is not None else None
        new_allowed = set(map(json.dumps, new.allowed_values or [])) if new.allowed_values is not None else None
        if old_allowed != new_allowed:
            if old_allowed is None and new_allowed is not None:
                cls = "breaking"
            elif old_allowed is not None and new_allowed is None:
                cls = "nonbreaking"
            elif old_allowed is not None and new_allowed is not None and new_allowed < old_allowed:
                cls = "breaking"
            else:
                cls = "potentially_breaking"
            changes.append(_change(f"rules.{column}.allowed_values", cls, old.allowed_values, new.allowed_values, "Approved values changed."))
        if old.maximum_age_hours != new.maximum_age_hours:
            cls = "breaking" if new.maximum_age_hours is not None and (old.maximum_age_hours is None or new.maximum_age_hours < old.maximum_age_hours) else "nonbreaking"
            changes.append(_change(f"rules.{column}.maximum_age_hours", cls, old.maximum_age_hours, new.maximum_age_hours, "Freshness requirement changed."))
        if old.description != new.description:
            changes.append(_change(f"rules.{column}.description", "documentation_only", old.description, new.description, "Rule documentation changed."))

    old_dataset_rules = {rule.name or f"unnamed:{index}:{rule.type}": rule for index, rule in enumerate(older.dataset_rules, 1)}
    new_dataset_rules = {rule.name or f"unnamed:{index}:{rule.type}": rule for index, rule in enumerate(newer.dataset_rules, 1)}
    for name in sorted(new_dataset_rules.keys() - old_dataset_rules.keys()):
        changes.append(_change(f"dataset_rules.{name}", "potentially_breaking", None, new_dataset_rules[name].model_dump(mode="json"), "A new dataset-level rule was introduced."))
    for name in sorted(old_dataset_rules.keys() - new_dataset_rules.keys()):
        changes.append(_change(f"dataset_rules.{name}", "nonbreaking", old_dataset_rules[name].model_dump(mode="json"), None, "A dataset-level constraint was removed."))
    for name in sorted(old_dataset_rules.keys() & new_dataset_rules.keys()):
        before = old_dataset_rules[name].model_dump(mode="json")
        after = new_dataset_rules[name].model_dump(mode="json")
        if before != after:
            changes.append(_change(f"dataset_rules.{name}", "potentially_breaking", before, after, "Dataset-level rule behavior changed."))

    highest: ChangeClass = "documentation_only"
    if changes:
        highest = max((item["classification"] for item in changes), key=lambda value: _CLASS_ORDER[value])
    return {
        "classification": highest if changes else "none",
        "change_count": len(changes),
        "changes": changes,
    }
