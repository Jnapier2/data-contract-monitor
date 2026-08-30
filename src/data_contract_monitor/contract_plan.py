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

    for column, column_rule in contract.rules.items():
        for suffix, active in (
            ("nullable", not column_rule.nullable),
            ("type", column_rule.data_type != "any"),
            ("unique", column_rule.unique),
            ("minimum", column_rule.minimum is not None),
            ("maximum", column_rule.maximum is not None),
            ("min_length", column_rule.min_length is not None),
            ("max_length", column_rule.max_length is not None),
            ("pattern", column_rule.pattern is not None),
            ("allowed_values", column_rule.allowed_values is not None),
            ("maximum_age_hours", column_rule.maximum_age_hours is not None),
        ):
            if active:
                rule_ids.append(f"column.{suffix}:{column}")

    for index, dataset_rule in enumerate(contract.dataset_rules, start=1):
        name = dataset_rule.name or f"dataset_rule_{index}"
        if name in dataset_rule_names:
            raise ContractPlanError(f"Duplicate dataset rule name '{name}'.")
        dataset_rule_names.add(name)
        rule_ids.append(f"dataset.{dataset_rule.type}:{name}")
        for referenced_column in dataset_rule.columns or []:
            referenced.add(referenced_column)
        for optional_column in (
            dataset_rule.column,
            dataset_rule.when_column,
            dataset_rule.then_column,
            dataset_rule.left_column,
        ):
            if optional_column:
                referenced.add(optional_column)
        if dataset_rule.type == "aggregate_reconciliation" and dataset_rule.right_expression:
            try:
                referenced.update(referenced_names(dataset_rule.right_expression))
            except ExpressionError as exc:
                raise ContractPlanError(str(exc)) from exc

    return CompiledContractPlan(
        contract=contract,
        required_columns=tuple(contract.dataset.required_columns),
        referenced_columns=tuple(sorted(referenced)),
        rule_ids=tuple(rule_ids),
    )
