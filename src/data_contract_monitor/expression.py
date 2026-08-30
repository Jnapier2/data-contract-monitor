from __future__ import annotations

import ast
from collections.abc import Mapping

import pandas as pd


class ExpressionError(ValueError):
    """Raised when a reconciliation expression is unsafe or invalid."""


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def referenced_names(expression: str) -> set[str]:
    tree = _parse(expression)
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def evaluate_numeric_expression(expression: str, columns: Mapping[str, pd.Series]) -> pd.Series:
    tree = _parse(expression)

    def visit(node: ast.AST) -> pd.Series | float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Name):
            if node.id not in columns:
                raise ExpressionError(f"Expression references missing column '{node.id}'.")
            return pd.to_numeric(columns[node.id], errors="coerce")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        raise ExpressionError(f"Unsupported expression element: {type(node).__name__}")

    value = visit(tree)
    if isinstance(value, pd.Series):
        return value
    if columns:
        first = next(iter(columns.values()))
        return pd.Series(value, index=first.index, dtype=float)
    return pd.Series(dtype=float)


def _parse(expression: str) -> ast.Expression:
    if not expression.strip():
        raise ExpressionError("Reconciliation expression cannot be empty.")
    if len(expression) > 512:
        raise ExpressionError("Reconciliation expression exceeds 512 characters.")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Invalid reconciliation expression: {exc.msg}") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, ast.Name, ast.Constant, ast.BinOp, ast.UnaryOp)):
            continue
        if isinstance(node, _ALLOWED_BINOPS + _ALLOWED_UNARYOPS):
            continue
        raise ExpressionError(f"Unsupported reconciliation syntax: {type(node).__name__}")
    return tree
