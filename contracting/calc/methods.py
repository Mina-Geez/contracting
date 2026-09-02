"""Dimension-driven quantity calculation methods.

This module is the single source of truth for HOW a billable quantity is derived
from a line's dimensions. The fixed methods are pure Python (no Frappe import) so
they can be unit-tested and run in the parity harness without a site. Only the
`formula` escape hatch touches Frappe (for `frappe.safe_eval`), and it imports
Frappe lazily.

Public API (stable — the parity harness and engine depend on this signature):

    compute(method_key, height=0.0, width=0.0, length=0.0,
            base_qty=1.0, waste_factor=1.0, formula=None) -> float | None

Semantics per method:
    area        -> height * width * base_qty
    perimeter   -> (height + width) * 2 * base_qty
    linear      -> length * base_qty
    piece_waste -> base_qty * waste_factor
    bom_driven  -> base_qty * waste_factor   (line qty only; component
                   explosion is handled by the item's BOM elsewhere)
    manual      -> None  (caller leaves the user-entered qty untouched)
    formula     -> frappe.safe_eval(formula, ...) with a locals dict restricted
                   to the declared dimensions + whitelisted math. Privileged.
"""

from __future__ import annotations

# --- Method keys (import these; never hard-code the strings elsewhere) --------
AREA = "area"
PERIMETER = "perimeter"
LINEAR = "linear"
PIECE_WASTE = "piece_waste"
BOM_DRIVEN = "bom_driven"
MANUAL = "manual"
FORMULA = "formula"

#: Ordered registry used to seed the Calculation Method DocType. Each entry
#: declares which dimension inputs the method consumes and its privilege.
STANDARD_METHODS = [
	{
		"method_key": AREA,
		"method_label": "Area (h × w × qty)",
		"description": "Billable area = height × width × base quantity. e.g. glass panels.",
		"requires_height": 1,
		"requires_width": 1,
		"requires_length": 0,
		"requires_base_qty": 1,
		"requires_waste_factor": 0,
		"is_formula": 0,
		"is_privileged": 0,
	},
	{
		"method_key": PERIMETER,
		"method_label": "Perimeter ((h + w) × 2 × qty)",
		"description": "Perimeter length = (height + width) × 2 × base quantity. e.g. framing/edging.",
		"requires_height": 1,
		"requires_width": 1,
		"requires_length": 0,
		"requires_base_qty": 1,
		"requires_waste_factor": 0,
		"is_formula": 0,
		"is_privileged": 0,
	},
	{
		"method_key": LINEAR,
		"method_label": "Linear (length × qty)",
		"description": "Linear metres = length × base quantity. e.g. profiles, rails.",
		"requires_height": 0,
		"requires_width": 0,
		"requires_length": 1,
		"requires_base_qty": 1,
		"requires_waste_factor": 0,
		"is_formula": 0,
		"is_privileged": 0,
	},
	{
		"method_key": PIECE_WASTE,
		"method_label": "Piece × waste factor",
		"description": "Quantity = base quantity × waste factor. e.g. cut-to-size with offcut allowance.",
		"requires_height": 0,
		"requires_width": 0,
		"requires_length": 0,
		"requires_base_qty": 1,
		"requires_waste_factor": 1,
		"is_formula": 0,
		"is_privileged": 0,
	},
	{
		"method_key": BOM_DRIVEN,
		"method_label": "BOM-driven",
		"description": "Line qty = base quantity × waste factor; components explode via the item's BOM.",
		"requires_height": 0,
		"requires_width": 0,
		"requires_length": 0,
		"requires_base_qty": 1,
		"requires_waste_factor": 1,
		"is_formula": 0,
		"is_privileged": 0,
	},
	{
		"method_key": MANUAL,
		"method_label": "Manual",
		"description": "No automatic calculation; the user-entered quantity is kept as-is.",
		"requires_height": 0,
		"requires_width": 0,
		"requires_length": 0,
		"requires_base_qty": 0,
		"requires_waste_factor": 0,
		"is_formula": 0,
		"is_privileged": 0,
	},
	{
		"method_key": FORMULA,
		"method_label": "Formula (advanced)",
		"description": "Privileged escape hatch: a safe_eval expression over the declared dimensions.",
		"requires_height": 0,
		"requires_width": 0,
		"requires_length": 0,
		"requires_base_qty": 0,
		"requires_waste_factor": 0,
		"is_formula": 1,
		"is_privileged": 1,
	},
]

#: Convenience set of the built-in keys.
STANDARD_METHOD_KEYS = {m["method_key"] for m in STANDARD_METHODS}


def _f(value) -> float:
	"""Coerce to float, treating None/""/invalid as 0.0."""
	if value is None or value == "":
		return 0.0
	try:
		return float(value)
	except (TypeError, ValueError):
		return 0.0


def compute(
	method_key: str,
	height: float = 0.0,
	width: float = 0.0,
	length: float = 0.0,
	base_qty: float = 1.0,
	waste_factor: float = 1.0,
	formula: str | None = None,
):
	"""Return the billable quantity for ``method_key``.

	Returns ``None`` for the ``manual`` method (the caller must leave qty
	untouched). Raises ``ValueError`` for an unknown method key, and (for the
	formula method) surfaces evaluation errors from ``frappe.safe_eval``.
	"""
	h, w, ln = _f(height), _f(width), _f(length)
	bq, wf = _f(base_qty), _f(waste_factor)

	if method_key == AREA:
		return h * w * bq
	if method_key == PERIMETER:
		return (h + w) * 2.0 * bq
	if method_key == LINEAR:
		return ln * bq
	if method_key == PIECE_WASTE:
		return bq * wf
	if method_key == BOM_DRIVEN:
		return bq * wf
	if method_key == MANUAL:
		return None
	if method_key == FORMULA:
		return evaluate_formula(
			formula,
			{"height": h, "width": w, "length": ln, "base_qty": bq, "waste_factor": wf},
		)

	raise ValueError(f"Unknown calculation method: {method_key!r}")


# --- Formula escape hatch -----------------------------------------------------
# Whitelisted math helpers exposed to formula authors. Passing them as *locals*
# (values) rather than relying on builtins keeps the sandbox surface explicit.
def _safe_math_locals() -> dict:
	import math

	return {
		"abs": abs,
		"round": round,
		"min": min,
		"max": max,
		"pow": pow,
		"sqrt": math.sqrt,
		"ceil": math.ceil,
		"floor": math.floor,
		"pi": math.pi,
	}


def evaluate_formula(formula: str | None, dimensions: dict) -> float:
	"""Evaluate a configured formula string server-side via ``frappe.safe_eval``.

	``dimensions`` supplies the only variables in scope (height, width, length,
	base_qty, waste_factor) plus whitelisted math helpers. Security depends
	entirely on this restricted locals dict — do not widen it.
	"""
	if not formula or not str(formula).strip():
		raise ValueError("Formula method selected but no formula expression is configured.")

	import frappe  # lazy: pure methods above stay import-free for offline tests

	eval_locals = {}
	eval_locals.update(dimensions)
	eval_locals.update(_safe_math_locals())

	try:
		result = frappe.safe_eval(str(formula), eval_globals=None, eval_locals=eval_locals)
	except Exception as exc:  # noqa: BLE001 - re-raise as a clear, user-facing error
		frappe.throw(
			frappe._("Invalid calculation formula: {0}").format(str(exc)),
			title=frappe._("Formula Error"),
		)
		raise  # unreachable; keeps type-checkers happy

	return _f(result)
