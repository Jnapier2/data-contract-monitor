from __future__ import annotations

from dataclasses import dataclass

from .expression import ExpressionError, referenced_names
from .models import Contract


class ContractPlanError(ValueError):
    """Raised when a valid contract cannot produce an unambiguous execution plan."""


@dataclass(frozen=True)
class CompiledContractPlan:
    contract: Contract
    required_columns: tuple[str, ...]
    referenced_columns: tuple[str, ...]
    rule_ids: tuple[str, ...]


def compile_contract(contract: Contract) -> CompiledContractPlan:
    referenced = set(contract.dataset.required_columns) | set(contract.rules)
    rule_ids: list[str] = []
    dataset_rule_names: set[str] = set()

    for column, rule in contract.rules.items():
        for suffix, active in (
            ("nullable", not rule.nullable),
            ("type", rule.data_type != "any"),
            ("unique", rule.unique),
            ("minimum", rule.minimum is not None),
            ("maximum", rule.maximum is not None),
            ("min_length", rule.min_length is not None),
            ("max_length", rule.max_length is not None),
            ("pattern", rule.pattern is not None),
            ("allowed_values", rule.allowed_values is not None),
            ("maximum_age_hours", rule.maximum_age_hours is not None),
        ):
            if active:
                rule_ids.append(f"column.{suffix}:{column}")

    for index, rule in enumerate(contract.dataset_rules, start=1):
        name = rule.name or f"dataset_rule_{index}"
        if name in dataset_rule_names:
            raise ContractPlanError(f"Duplicate dataset rule name '{name}'.")
        dataset_rule_names.add(name)
        rule_ids.append(f"dataset.{rule.type}:{name}")
        for column in rule.columns or []:
            referenced.add(column)
        for column in (rule.column, rule.when_column, rule.then_column, rule.left_column):
            if column:
                referenced.add(column)
        if rule.type == "aggregate_reconciliation" and rule.right_expression:
            try:
                referenced.update(referenced_names(rule.right_expression))
            except ExpressionError as exc:
                raise ContractPlanError(str(exc)) from exc

    return CompiledContractPlan(
        contract=contract,
        required_columns=tuple(contract.dataset.required_columns),
        referenced_columns=tuple(sorted(referenced)),
        rule_ids=tuple(rule_ids),
    )
