"""Pure, framework-free measurement engine (the correctness oracle core).

No Frappe import: unit-testable and runnable offline. `compute` returns the
billable quantity for a measure; `manual` returns None (caller keeps the
user-entered qty). Formulas are evaluated by a restricted AST walker — never
`eval`/`exec` — over the plain-words tokens only.

Note on blank inputs: Frappe Float fields store a blank as 0, so a blank and an
explicit 0 are indistinguishable here. `count` and `wastage` therefore treat 0
as "not given" and fall back to 1 (one unit / no wastage allowance).
"""
from __future__ import annotations

import ast
import math

AREA = "area"; PERIMETER = "perimeter"; LINEAR = "linear"
COUNT = "count"; PIECE_WASTE = "piece_waste"; MANUAL = "manual"; FORMULA = "formula"
MEASURE_KEYS = {AREA, PERIMETER, LINEAR, COUNT, PIECE_WASTE, MANUAL, FORMULA}

#: The plain words a formula author may use.
FORMULA_TOKENS = ("height", "width", "length", "count", "wastage")

_ALLOWED_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max, "pow": pow,
    "sqrt": math.sqrt, "ceil": math.ceil, "floor": math.floor,
}
_ALLOWED_CONSTS = {"pi": math.pi}
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def compute(measure, *, height=0.0, width=0.0, length=0.0, count=1.0,
            wastage=1.0, formula=None):
    """Return the billable quantity for `measure`, or None for `manual`."""
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
        return evaluate_formula(formula, {"height": h, "width": w, "length": ln,
                                          "count": c, "wastage": wf})
    raise ValueError(f"Unknown measure: {measure!r}")


def validate_formula(formula):
    """Check a formula's syntax, names and constructs without doing the maths.

    Used at save time so a bad formula is rejected immediately. It deliberately
    does NOT evaluate arithmetic: a valid formula like `count / (width - height)`
    would divide by zero against sample values and must not be rejected for that.
    Raises ValueError when the formula cannot ever be evaluated safely.
    """
    if not formula or not str(formula).strip():
        raise ValueError("Formula is empty")
    try:
        tree = ast.parse(str(formula), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid formula syntax: {e}") from e
    _check_node(tree)


def evaluate_formula(formula, tokens):
    """Evaluate a plain-words formula over `tokens` (height/width/…)."""
    if not formula or not str(formula).strip():
        raise ValueError("Formula is empty")
    try:
        tree = ast.parse(str(formula), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid formula syntax: {e}") from e
    return _f(_eval_node(tree, dict(tokens)))


# --- internals ---------------------------------------------------------------

def _f(value) -> float:
    """Coerce to float; None/blank/garbage become 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _check_node(node, names=FORMULA_TOKENS):
    """Structural validation: same rules as _eval_node, without computing."""
    if isinstance(node, ast.Expression):
        return _check_node(node.body, names)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return
        raise ValueError("Only numeric literals are allowed")
    if isinstance(node, ast.Name):
        if node.id in names or node.id in _ALLOWED_CONSTS:
            return
        raise ValueError(f"Unknown name in formula: {node.id!r}")
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        _check_node(node.left, names)
        _check_node(node.right, names)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
        return _check_node(node.operand, names)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ValueError("Only whitelisted functions are allowed")
        if node.keywords:
            raise ValueError("Keyword arguments are not allowed in formulas")
        for arg in node.args:
            _check_node(arg, names)
        return
    raise ValueError("Unsupported expression in formula")


def _eval_node(node, names):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
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
