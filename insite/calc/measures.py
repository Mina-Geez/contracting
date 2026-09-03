"""Pure, framework-free measurement engine (the correctness oracle core).

No Frappe import: unit-testable and runnable offline.

A rule is a **formula over named inputs**. Each input names a field on the
transaction line and gives it a short name; the formula combines those names.
The presets below are nothing more than a starting pair of inputs and formula
for the arithmetic most trades need, so there is one mechanism, not two.

Two things worth knowing before changing this file:

* **Validation and evaluation share one walker.** `validate_formula` runs
  `_walk` with `evaluate=False`. If they were separate walkers they could drift,
  and a formula accepted at save time would behave differently on a customer's
  invoice. Add a node type once and both paths get it.
* **Blank vs zero.** A Frappe Float stores a blank as 0, so the two are
  indistinguishable here. The engine decides what an empty line means; this
  module just evaluates what it is given.
"""

from __future__ import annotations

import ast
import math
import re

#: A formula refers to its inputs by these names.
TOKEN_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")

#: Ready-made starting points. Each names the inputs it expects — by token and
#: by the Insite field that usually supplies it — and the formula over them.
PRESETS = {
	"Area": {
		"inputs": [("height", "custom_height"), ("width", "custom_width"), ("count", "custom_base_qty")],
		"formula": "height * width * count",
	},
	"Perimeter": {
		"inputs": [("height", "custom_height"), ("width", "custom_width"), ("count", "custom_base_qty")],
		"formula": "(height + width) * 2 * count",
	},
	"Linear": {
		"inputs": [("length", "custom_length"), ("count", "custom_base_qty")],
		"formula": "length * count",
	},
	"Count": {
		"inputs": [("count", "custom_base_qty")],
		"formula": "count",
	},
	"Piece × Wastage": {
		"inputs": [("count", "custom_base_qty"), ("wastage", "custom_waste_factor")],
		"formula": "count * wastage",
	},
	"Volume": {
		"inputs": [
			("height", "custom_height"),
			("width", "custom_width"),
			("length", "custom_length"),
			("count", "custom_base_qty"),
		],
		"formula": "height * width * length * count",
	},
}

#: Chosen on a rule when the quantity is typed by hand and never calculated.
MANUAL = "Manual"

#: Chosen when the formula is written from scratch.
CUSTOM = "Custom"

#: Everything the Preset field may hold.
PRESET_CHOICES = (*PRESETS.keys(), MANUAL, CUSTOM)

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
	"abs": abs,
	"round": round,
	"min": min,
	"max": max,
	"pow": _guarded_pow,
	"sqrt": math.sqrt,
	"ceil": math.ceil,
	"floor": math.floor,
}
#: (minimum args, maximum args) — None means "no maximum".
_FUNC_ARITY = {
	"abs": (1, 1),
	"round": (1, 2),
	"min": (1, None),
	"max": (1, None),
	"pow": (2, 2),
	"sqrt": (1, 1),
	"ceil": (1, 1),
	"floor": (1, 1),
}
_ALLOWED_CONSTS = {"pi": math.pi}
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def suggest_token(label):
	"""Turn a field label into a name a formula can use: 'Number of Panels' -> 'number_of_panels'."""
	token = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
	if not token or token[0].isdigit():
		token = f"f_{token}" if token else "field"
	return token


def is_valid_token(token):
	return bool(token) and bool(TOKEN_PATTERN.match(token))


def validate_formula(formula, tokens):
	"""Check a formula can always be run, without running the arithmetic.

	`tokens` is the set of names the rule's inputs provide. Deliberately does
	not compute: `count / (width - height)` is a legitimate formula that would
	divide by zero against sample values, and rejecting it at save time would
	be wrong.
	"""
	_walk(_parse(formula), {token: 0.0 for token in tokens}, evaluate=False)


def evaluate_formula(formula, values):
	"""Evaluate a formula over `values`, a mapping of token name to number.

	Values are coerced here, so a blank field reads as zero rather than failing
	the arithmetic.
	"""
	numbers = {token: _f(value) for token, value in (values or {}).items()}
	result = _walk(_parse(formula), numbers, evaluate=True)
	value = _f(result)
	if not math.isfinite(value):
		raise ValueError("This formula produced a number too large to use.")
	return value


def formula_tokens(formula):
	"""Every name a formula refers to, so a rule can be checked against its inputs."""
	try:
		tree = ast.parse(str(formula or ""), mode="eval")
	except SyntaxError:
		return set()
	return {
		node.id
		for node in ast.walk(tree)
		if isinstance(node, ast.Name) and node.id not in _ALLOWED_FUNCS and node.id not in _ALLOWED_CONSTS
	}


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
		if node.id in names:
			return names[node.id] if evaluate else None
		known = ", ".join(sorted(names)) or "none yet"
		raise ValueError(f"The formula uses '{node.id}', which is not one of this rule's inputs ({known}).")

	if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
		if isinstance(node.op, ast.Pow):
			_check_static_power(node.left, node.right)
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
			raise ValueError("You can use these functions only: " + ", ".join(sorted(_ALLOWED_FUNCS)) + ".")
		if node.keywords:
			raise ValueError("Write the values in order, for example round(height * width, 2).")
		_check_arity(name, len(node.args))
		if name == "pow":
			_check_static_power(node.args[0], node.args[1])
		args = [_walk(a, names, evaluate) for a in node.args]
		return _ALLOWED_FUNCS[name](*args) if evaluate else None

	raise ValueError(
		"Insite cannot read part of this formula. Use numbers, the rule's inputs, "
		"the signs + - * / %, and the allowed functions."
	)


def _check_arity(name, given):
	low, high = _FUNC_ARITY[name]
	if given < low or (high is not None and given > high):
		expected = f"{low}" if high == low else (f"{low} or more" if high is None else f"{low} to {high}")
		raise ValueError(f"{name}() needs {expected} value(s), but {given} were given.")


def _check_static_power(base_node, exponent_node):
	"""Reject a power whose size can be worked out without the measurements."""
	exponent = _static_value(exponent_node)
	base = _static_value(base_node)
	if (exponent is not None and abs(exponent) > MAX_EXPONENT) or (base is not None and abs(base) > MAX_BASE):
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
