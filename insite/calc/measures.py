"""Pure, framework-free measurement engine (the correctness oracle core).

No Frappe import: unit-testable and runnable offline. `compute` returns the
billable quantity for a measure; `manual` returns None (caller keeps the
user-entered qty). Formulas are walked by a restricted AST evaluator — never
`eval`/`exec` — over the plain-words tokens only.

Two things worth knowing before changing this file:

* **Validation and evaluation share one walker.** `validate_formula` runs
  `_walk` with `evaluate=False`. If they were separate walkers they could drift,
  and a formula accepted at save time would behave differently on a customer's
  invoice. Add a node type once and both paths get it.
* **Blank vs zero.** A Frappe Float stores a blank as 0, so the two are
  indistinguishable here. For measures where the value is only a *multiplier*
  (area, perimeter, linear) a 0 means "not given" and falls back to 1. For
  `count` and `piece_waste` the count IS the quantity, so a 0 stays 0 — turning
  it into 1 would invent a unit nobody ordered.
"""
from __future__ import annotations

import ast
import math

AREA = "area"
PERIMETER = "perimeter"
LINEAR = "linear"
COUNT = "count"
PIECE_WASTE = "piece_waste"
MANUAL = "manual"
FORMULA = "formula"
MEASURE_KEYS = {AREA, PERIMETER, LINEAR, COUNT, PIECE_WASTE, MANUAL, FORMULA}

#: What the user picks and what gets stamped on the line. The stored value is
#: the label — contractors never see a snake_case key — and everything inside
#: the engine works from the key.
MEASURE_LABELS = {
	AREA: "Area (Height × Width × Count)",
	PERIMETER: "Perimeter ((Height + Width) × 2 × Count)",
	LINEAR: "Linear (Length × Count)",
	COUNT: "Count",
	PIECE_WASTE: "Piece × Wastage (Count × Wastage)",
	MANUAL: "Manual (keep the typed quantity)",
	FORMULA: "Custom formula",
}
LABEL_TO_KEY = {label: key for key, label in MEASURE_LABELS.items()}

#: The plain words a formula author may use.
FORMULA_TOKENS = ("height", "width", "length", "count", "wastage")

# Guards against a formula that is valid but ruinous to run. A Contracting
# Manager authors formulas; ordinary users trigger them on every save, so an
# unbounded exponent would be a denial of service planted by one role and
# detonated by another.
MAX_EXPONENT = 64
MAX_BASE = 1e12
MAX_NODES = 200

def _guarded_pow(base, exponent, *rest):
	"""`pow` with the same ceiling as the ** operator."""
	if abs(_f(exponent)) > MAX_EXPONENT or abs(_f(base)) > MAX_BASE:
		raise ValueError(f"The power in this formula is too large (highest allowed is {MAX_EXPONENT}).")
	return pow(base, exponent, *rest)


_ALLOWED_FUNCS = {
	"abs": abs, "round": round, "min": min, "max": max, "pow": _guarded_pow,
	"sqrt": math.sqrt, "ceil": math.ceil, "floor": math.floor,
}
#: (minimum args, maximum args) — None means "no maximum".
_FUNC_ARITY = {
	"abs": (1, 1), "round": (1, 2), "min": (1, None), "max": (1, None),
	"pow": (2, 2), "sqrt": (1, 1), "ceil": (1, 1), "floor": (1, 1),
}
_ALLOWED_CONSTS = {"pi": math.pi}
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def normalize_measure(value):
	"""Accept either a stored label or an internal key; return the key."""
	if value in MEASURE_KEYS:
		return value
	return LABEL_TO_KEY.get(value, value)


def compute(measure, *, height=0.0, width=0.0, length=0.0, count=1.0,
            wastage=1.0, formula=None):
	"""Return the billable quantity for `measure`, or None for `manual`."""
	measure = normalize_measure(measure)
	h, w, ln = _f(height), _f(width), _f(length)
	wf = _f(wastage) or 1.0

	if measure == AREA:
		return h * w * (_f(count) or 1.0)
	if measure == PERIMETER:
		return (h + w) * 2.0 * (_f(count) or 1.0)
	if measure == LINEAR:
		return ln * (_f(count) or 1.0)
	if measure == COUNT:
		return _f(count)
	if measure == PIECE_WASTE:
		return _f(count) * wf
	if measure == MANUAL:
		return None
	if measure == FORMULA:
		return evaluate_formula(formula, {"height": h, "width": w, "length": ln,
		                                  "count": _f(count), "wastage": wf})
	raise ValueError(f"Unknown measure: {measure!r}")


def validate_formula(formula):
	"""Check a formula can always be run, without running the arithmetic.

	Deliberately does not compute: `count / (width - height)` is a legitimate
	formula that would divide by zero against sample values, and rejecting it
	at save time would be wrong. Raises ValueError with a message written for
	the person editing the rule.
	"""
	_walk(_parse(formula), {}, evaluate=False)


def evaluate_formula(formula, tokens):
	"""Evaluate a plain-words formula over `tokens` (height/width/…)."""
	result = _walk(_parse(formula), dict(tokens), evaluate=True)
	value = _f(result)
	if not math.isfinite(value):
		raise ValueError("This formula produced a number too large to use.")
	return value


# --- internals ---------------------------------------------------------------

def _f(value) -> float:
	"""Coerce to float; None/blank/garbage become 0.0."""
	if value is None or value == "":
		return 0.0
	try:
		return float(value)
	except (TypeError, ValueError, OverflowError):
		return 0.0


def _parse(formula) -> ast.Expression:
	if not formula or not str(formula).strip():
		raise ValueError("The formula is empty.")
	try:
		tree = ast.parse(str(formula), mode="eval")
	except SyntaxError as e:
		raise ValueError(f"Check the brackets and the signs in this formula ({e.msg}).") from e
	if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
		raise ValueError("This formula is too long. Split it into a simpler one.")
	return tree


def _walk(node, names, evaluate):
	"""Validate `node`, and compute it when `evaluate` is true.

	One walker serves both paths so a formula that saves can always run.
	"""
	if isinstance(node, ast.Expression):
		return _walk(node.body, names, evaluate)

	if isinstance(node, ast.Constant):
		if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
			raise ValueError("Use plain numbers, for example 1.1.")
		if not math.isfinite(float(node.value)):
			raise ValueError("Use plain numbers, for example 1.1.")
		return node.value if evaluate else None

	if isinstance(node, ast.Name):
		if node.id in _ALLOWED_CONSTS:
			return _ALLOWED_CONSTS[node.id] if evaluate else None
		if node.id in FORMULA_TOKENS:
			return names.get(node.id, 0.0) if evaluate else None
		raise ValueError(
			f"The formula uses the word '{node.id}'. You can use these words only: "
			+ ", ".join(FORMULA_TOKENS) + "."
		)

	if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
		if isinstance(node.op, ast.Pow):
			_check_exponent(node)
		left = _walk(node.left, names, evaluate)
		right = _walk(node.right, names, evaluate)
		return _apply_binop(node.op, left, right) if evaluate else None

	if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
		value = _walk(node.operand, names, evaluate)
		if not evaluate:
			return None
		return +value if isinstance(node.op, ast.UAdd) else -value

	if isinstance(node, ast.Call):
		name = node.func.id if isinstance(node.func, ast.Name) else None
		if name not in _ALLOWED_FUNCS:
			raise ValueError(
				"You can use these functions only: " + ", ".join(sorted(_ALLOWED_FUNCS)) + "."
			)
		if node.keywords:
			raise ValueError("Write the values in order, for example round(height * width, 2).")
		_check_arity(name, len(node.args))
		if name == "pow":
			_check_static_power(node.args[0], node.args[1])
		args = [_walk(a, names, evaluate) for a in node.args]
		return _ALLOWED_FUNCS[name](*args) if evaluate else None

	raise ValueError(
		"Insite cannot read part of this formula. Use numbers, the words "
		+ ", ".join(FORMULA_TOKENS) + ", the signs + - * / %, and the allowed functions."
	)


def _check_arity(name, given):
	low, high = _FUNC_ARITY[name]
	if given < low or (high is not None and given > high):
		expected = f"{low}" if high == low else (f"{low} or more" if high is None else f"{low} to {high}")
		raise ValueError(f"{name}() needs {expected} value(s), but {given} were given.")


def _check_exponent(node):
	"""Reject an exponent big enough to hang a worker, at save time.

	`**` binds right to left, so `9 ** 9 ** 9` hides its real exponent behind
	another power. Anything built only from numbers is folded here — in floats,
	so the check itself cannot blow up — and an exponent that depends on a
	measurement is left to the runtime guard in `_apply_binop`.
	"""
	_check_static_power(node.left, node.right)


def _check_static_power(base_node, exponent_node):
	"""Reject a power whose size can be worked out without the measurements."""
	exponent = _static_value(exponent_node)
	base = _static_value(base_node)
	if (exponent is not None and abs(exponent) > MAX_EXPONENT) or \
			(base is not None and abs(base) > MAX_BASE):
		raise ValueError(f"The power in this formula is too large (highest allowed is {MAX_EXPONENT}).")


def _static_value(node):
	"""The value of a numbers-only subtree, or None when it depends on inputs."""
	if isinstance(node, ast.Constant):
		if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
			return None
		return float(node.value)
	if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
		inner = _static_value(node.operand)
		if inner is None:
			return None
		return +inner if isinstance(node.op, ast.UAdd) else -inner
	if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
		left, right = _static_value(node.left), _static_value(node.right)
		if left is None or right is None:
			return None
		if isinstance(node.op, ast.Pow) and (abs(right) > MAX_EXPONENT or abs(left) > MAX_BASE):
			raise ValueError(f"The power in this formula is too large (highest allowed is {MAX_EXPONENT}).")
		try:
			value = float(_apply_binop(node.op, left, right))
		except (ArithmeticError, OverflowError, ValueError):
			return None
		return value if math.isfinite(value) else None
	return None


_BINOPS = {
	ast.Add: lambda a, b: a + b,
	ast.Sub: lambda a, b: a - b,
	ast.Mult: lambda a, b: a * b,
	ast.Div: lambda a, b: a / b,
	ast.FloorDiv: lambda a, b: a // b,
	ast.Mod: lambda a, b: a % b,
}


def _apply_binop(op, a, b):
	if isinstance(op, ast.Pow):
		return _guarded_pow(a, b)
	operation = _BINOPS.get(type(op))
	if operation is None:
		raise ValueError("Insite cannot read part of this formula.")
	return operation(a, b)
