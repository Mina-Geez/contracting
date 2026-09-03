"""Pure, framework-free measurement engine (the correctness oracle core).

No Frappe import: unit-testable and runnable offline. `compute` returns the
billable quantity for a measure; `manual` returns None (caller keeps the
user-entered qty). Formula uses a restricted AST evaluator (see Task 3).
"""
from __future__ import annotations

AREA = "area"; PERIMETER = "perimeter"; LINEAR = "linear"
COUNT = "count"; PIECE_WASTE = "piece_waste"; MANUAL = "manual"; FORMULA = "formula"
MEASURE_KEYS = {AREA, PERIMETER, LINEAR, COUNT, PIECE_WASTE, MANUAL, FORMULA}


def _f(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compute(measure, *, height=0.0, width=0.0, length=0.0, count=1.0,
            wastage=1.0, formula=None):
    h, w, ln = _f(height), _f(width), _f(length)
    c = _f(count) or 1.0
    wf = _f(wastage) or 1.0
    if measure == AREA:
        return h * w * c
    if measure == PERIMETER:
        return (h + w) * 2.0 * c
    if measure == LINEAR:
        return ln * c
    if measure == COUNT:
        return c
    if measure == PIECE_WASTE:
        return c * wf
    if measure == MANUAL:
        return None
    if measure == FORMULA:
        from insite.calc.measures import evaluate_formula  # self-import ok
        return evaluate_formula(formula, {"height": h, "width": w, "length": ln,
                                          "count": c, "wastage": wf})
    raise ValueError(f"Unknown measure: {measure!r}")


import ast
import math

_ALLOWED_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max, "pow": pow,
    "sqrt": math.sqrt, "ceil": math.ceil, "floor": math.floor,
}
_ALLOWED_CONSTS = {"pi": math.pi}
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def _eval_node(node, names):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric literals are allowed")
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        if node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        raise ValueError(f"Unknown name in formula: {node.id!r}")
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        return _apply_binop(node.op, _eval_node(node.left, names), _eval_node(node.right, names))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
        v = _eval_node(node.operand, names)
        return +v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ValueError("Only whitelisted functions are allowed")
        if node.keywords:
            raise ValueError("Keyword arguments are not allowed in formulas")
        args = [_eval_node(a, names) for a in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)
    raise ValueError("Unsupported expression in formula")


def _apply_binop(op, a, b):
    if isinstance(op, ast.Add): return a + b
    if isinstance(op, ast.Sub): return a - b
    if isinstance(op, ast.Mult): return a * b
    if isinstance(op, ast.Div): return a / b
    if isinstance(op, ast.FloorDiv): return a // b
    if isinstance(op, ast.Mod): return a % b
    if isinstance(op, ast.Pow): return a ** b
    raise ValueError("Unsupported operator")


def evaluate_formula(formula, tokens):
    if not formula or not str(formula).strip():
        raise ValueError("Formula is empty")
    try:
        tree = ast.parse(str(formula), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid formula syntax: {e}") from e
    return _f(_eval_node(tree, dict(tokens)))
