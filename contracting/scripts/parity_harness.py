# Copyright (c) 2026, Contracting Vertical and contributors
# For license information, please see license.txt
"""Parity regression harness for the contracting calc engine.

Pure calculation regression: it evaluates ``contracting.calc.methods.compute`` against a
catalogue of input->output cases and reports pass/fail. It performs **no database access
and no mutation** — it is safe to run on any site (staging clone), and it never touches
production data.

Populate ``parity_cases.json`` from real submitted documents on the clone (see PARITY.md),
then::

    bench --site <clone> execute contracting.scripts.parity_harness.run \
          --kwargs "{'cases_file':'parity_cases.json'}"

Run with no arguments to self-demo against the built-in UNVERIFIED seed cases.
"""

from __future__ import annotations

import json
import math

from contracting.calc.methods import compute

# UNVERIFIED seed cases — mirror the tables in PARITY.md. Replace with real clone data.
SAMPLE_CASES = [
	{"case_id": "AREA-01", "method_key": "area", "height": 1.2, "width": 2.4, "base_qty": 3,
	 "expected_qty": 8.64, "rate": 450, "expected_amount": 3888.00, "tol": 0.005},
	{"case_id": "AREA-02", "method_key": "area", "height": 0.9, "width": 2.1, "base_qty": 2,
	 "expected_qty": 3.78, "rate": 450, "expected_amount": 1701.00, "tol": 0.005},
	{"case_id": "PERI-01", "method_key": "perimeter", "height": 1.2, "width": 2.4, "base_qty": 3,
	 "expected_qty": 21.6, "rate": 30, "expected_amount": 648.00, "tol": 0.005},
	{"case_id": "LIN-01", "method_key": "linear", "length": 6.0, "base_qty": 5,
	 "expected_qty": 30.0, "rate": 40, "expected_amount": 1200.00, "tol": 0.005},
	{"case_id": "PW-01", "method_key": "piece_waste", "base_qty": 100, "waste_factor": 1.1,
	 "expected_qty": 110.0, "rate": 12, "expected_amount": 1320.00, "tol": 0.005},
	{"case_id": "BOM-01", "method_key": "bom_driven", "base_qty": 20, "waste_factor": 1.0,
	 "expected_qty": 20.0, "tol": 0.005},
	{"case_id": "MAN-01", "method_key": "manual", "expected_qty": 7, "rate": 200,
	 "expected_amount": 1400.00, "tol": 0.005},
	{"case_id": "FML-01", "method_key": "formula", "formula": "height*width*base_qty*1.1",
	 "height": 1.2, "width": 2.4, "base_qty": 3, "expected_qty": 9.504, "rate": 450,
	 "expected_amount": 4276.80, "tol": 0.005},
]

_DIM_KEYS = ("height", "width", "length", "base_qty", "waste_factor", "formula")


def _close(a, b, tol):
	return abs((a if a is not None else 0.0) - (b if b is not None else 0.0)) <= tol


def _eval_case(case, default_tol):
	"""Return a result dict for a single case."""
	case_id = case.get("case_id", "?")
	method = case["method_key"]
	tol = float(case.get("tol", default_tol))
	kwargs = {k: case[k] for k in _DIM_KEYS if k in case and case[k] is not None}

	res = {"case_id": case_id, "method_key": method, "tol": tol, "ok": False, "detail": ""}

	try:
		got_qty = compute(method, **kwargs)
	except Exception as exc:  # noqa: BLE401 - surface engine errors as failures
		res["detail"] = f"compute() raised: {exc!r}"
		return res

	# manual: engine returns None and leaves the user-entered qty untouched.
	if method == "manual":
		res["got_qty"] = None
		res["expected_qty"] = case.get("expected_qty")
		res["ok"] = got_qty is None
		res["detail"] = "manual: qty left as entered" if res["ok"] else f"expected None, got {got_qty}"
		return res

	exp_qty = case.get("expected_qty")
	res["got_qty"] = got_qty
	res["expected_qty"] = exp_qty

	if exp_qty is None:
		res["detail"] = "no expected_qty recorded (UNVERIFIED template)"
		return res

	qty_ok = got_qty is not None and _close(float(got_qty), float(exp_qty), tol)

	amt_ok = True
	if "rate" in case and case.get("expected_amount") is not None and got_qty is not None:
		got_amt = float(got_qty) * float(case["rate"])
		res["got_amount"] = round(got_amt, 6)
		res["expected_amount"] = float(case["expected_amount"])
		amt_ok = _close(got_amt, float(case["expected_amount"]), tol)

	res["ok"] = bool(qty_ok and amt_ok)
	if not res["ok"]:
		parts = []
		if not qty_ok:
			parts.append(f"qty {got_qty} != expected {exp_qty} (tol {tol})")
		if not amt_ok:
			parts.append(f"amount {res.get('got_amount')} != expected {res.get('expected_amount')}")
		res["detail"] = "; ".join(parts)
	else:
		res["detail"] = "ok"
	return res


def run(cases_file=None, cases=None, tol=1e-6):
	"""Evaluate parity cases and print a summary.

	:param cases_file: path to a JSON file (list of case dicts). Optional.
	:param cases: an in-memory list of case dicts. Optional.
	:param tol: default absolute tolerance when a case omits ``tol``.
	:returns: ``{"ok": bool, "total": int, "passed": int, "failed": int,
	            "skipped": int, "results": [...]}``.
	"""
	if cases is None:
		if cases_file:
			with open(cases_file, encoding="utf-8") as fh:
				cases = json.load(fh)
		else:
			cases = SAMPLE_CASES
			print("[parity] no cases supplied — running built-in UNVERIFIED seed cases\n")

	results = [_eval_case(c, tol) for c in cases]

	passed = sum(1 for r in results if r["ok"])
	skipped = sum(1 for r in results if not r["ok"] and "UNVERIFIED" in r["detail"])
	failed = len(results) - passed - skipped

	width_id = max((len(r["case_id"]) for r in results), default=7)
	print(f"{'CASE':<{width_id}}  {'METHOD':<12}  {'RESULT':<8}  DETAIL")
	print("-" * (width_id + 40))
	for r in results:
		status = "PASS" if r["ok"] else ("SKIP" if "UNVERIFIED" in r["detail"] else "FAIL")
		print(f"{r['case_id']:<{width_id}}  {r['method_key']:<12}  {status:<8}  {r['detail']}")

	print("-" * (width_id + 40))
	print(f"total={len(results)}  passed={passed}  failed={failed}  skipped(UNVERIFIED)={skipped}")

	return {
		"ok": failed == 0,
		"total": len(results),
		"passed": passed,
		"failed": failed,
		"skipped": skipped,
		"results": results,
	}


if __name__ == "__main__":
	summary = run()
	raise SystemExit(0 if summary["ok"] else 1)
