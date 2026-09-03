# Insite v1 (Delivery Spine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Insite contracting app (v1 "delivery spine") on Frappe/ERPNext v16 — a config-driven measurement engine, Project-anchored Scope Items, Variation Orders, Project+Scope enforcement on Sales Orders, and a Contract Progress report.

**Architecture:** A Frappe app `insite` layered on ERPNext's transactions/GL/Accounting Dimensions. A pure, framework-free calc core (measures + plain-words formula + rule resolution) is wrapped by Frappe doc-event hooks that compute billable quantities server-side in `before_validate`. Work Item Type is the config aggregate root (owns its Measurement Rules); Scope Item backs the `scope_item` Accounting Dimension and rolls up in the Contract Progress report.

**Tech Stack:** Frappe Framework v16, ERPNext v16, Python 3.12, Frappe DocTypes (JSON + controller `.py`), code-defined Custom Fields, Script Report, client scripts (vanilla JS), plain-Python unit tests.

**Spec:** `docs/specs/2026-09-03-insite-v1-delivery-spine-design.md` (read it alongside this plan).

## Global Constraints

- **Platform:** Frappe/ERPNext **v16**; app installs on branch `version-16` sites. App name `insite`; module name `Insite`.
- **Repo/branch:** build on a fresh branch `insite` in the existing `Mina-Geez/contracting` repo. The old `contracting` app stays on `version-16`.
- **No `bench`/site in this environment.** Pure-logic tasks are TDD'd offline; Frappe-integrated tasks are validated by `python -m py_compile` + JSON parse; end-to-end is verified on the Frappe Cloud test site (contra.k.frappe.cloud) over the "Contra test mcp" connector **after the user redeploys** (final task).
- **Architecture rules (hard):** no `db_set`; no fixtures of standard doctypes; no Export-Customizations `custom/*.json` sync; documented APIs only; all custom fields / dimension / roles / settings created idempotently in code. Server-authoritative calc in `before_validate`.
- **No implementor-facing fieldnames/codes:** identifiers are auto-numbers + plain Titles; configuration is dropdowns/toggles; formulas use plain words (Height, Width, Length, Count, Wastage).
- **Standard dimension fieldnames (fixed, app-owned):** inputs `custom_height`, `custom_width`, `custom_length`, `custom_base_qty` (label "Count"), `custom_waste_factor` (label "Wastage"); audit `custom_calculated_qty`, `custom_calc_measure`, `custom_calc_source`, `custom_calc_dimensions`; dimension `scope_item`.
- **Measure keys (stable):** `area`, `perimeter`, `linear`, `count`, `piece_waste`, `manual`, `formula`.
- **Formula tokens (stable, lowercase):** `height`, `width`, `length`, `count`, `wastage`; whitelisted funcs `abs round min max pow sqrt ceil floor` + `pi`.
- **Item child tables carrying dimensions (9):** Quotation Item, Sales Order Item, Delivery Note Item, Sales Invoice Item, Material Request Item, Supplier Quotation Item, Purchase Order Item, Purchase Receipt Item, Purchase Invoice Item.
- **Test runner:** each test file is pytest-compatible AND ends with a `if __name__ == "__main__"` runner, so `python -m pytest <file> -v` or `python <file>` both work with zero external deps.
- **DocType JSON wrapper convention (applies to every DocType JSON in this plan):** each `<doctype>.json` includes the standard keys `"doctype": "DocType"`, `"engine": "InnoDB"`, `"editable_grid": 1`, `"module": "Insite"`, `"creation"/"modified": "2026-09-03 00:00:00.000000"`, `"owner"/"modified_by": "Administrator"`, `"sort_field": "modified"`, `"sort_order": "DESC"`, plus the task-specific `name`, `autoname`/`issingle`/`istable`, `field_order`, `fields`, and `permissions`. Tasks below give the task-specific keys; wrap them with these standard keys.
- **Commit style:** conventional commits (`feat:`, `test:`, `chore:`, `docs:`); commit at the end of each task (and after each green test in TDD tasks).
- **Validation commands (offline):**
  - Compile: `python -m py_compile $(git ls-files '*.py')`
  - JSON parse: `python -c "import json,glob,sys; [json.load(open(f,encoding='utf-8')) for f in glob.glob('insite/**/*.json', recursive=True)]; print('json ok')"`
  - Tests: `python -m pytest insite/tests -v` (or run each file directly).

## File Structure

```
insite/                                  # repo root on branch `insite`  (the Frappe app repo)
  pyproject.toml                         # app metadata (name=insite)
  README.md  license.txt  .gitignore
  docs/specs/… docs/superpowers/plans/…  # spec + this plan
  docs/SETUP.md  docs/CONCEPTS.md
  insite/                                # app package
    __init__.py                          # __version__
    hooks.py                             # app_name, doc_events, doctype_js, after_install/migrate
    modules.txt                          # "Insite"
    patches.txt
    install.py                           # idempotent setup
    calc/
      __init__.py
      measures.py                        # PURE: measures + plain-words formula evaluator
      resolve.py                         # PURE: most-specific-wins rule resolution
      engine.py                          # Frappe glue: load rules, apply to rows, recalc doc
    config/
      __init__.py
      custom_fields.py                   # code-defined dimension + audit fields
      accounting_dimension.py            # scope_item dimension
      price_visibility.py                # settings-driven permlevel raise
    overrides/
      __init__.py
      transaction.py                     # before_validate recompute + Project/Scope enforcement
    insite/                              # module "Insite"
      doctype/
        work_item_type/ measurement_rule/ insite_type_account/
        scope_item/
        variation_order/ variation_line/
        contracting_settings/ contracting_price_role/
      report/contract_progress/          # .json .py .js
      workspace/insite/                  # workspace.json
    public/js/
      insite_transaction.js              # line dimension visibility on transactions
      work_item_type.js                  # "Test measure" button
    locale/ar.po
    tests/
      __init__.py
      test_measures.py                   # PURE (TDD)
      test_formula.py                    # PURE (TDD)
      test_resolve.py                    # PURE (TDD)
      test_parity.py                     # PURE — oracle vs new engine
```

---

### Task 1: App skeleton on branch `insite`

**Files:**
- Create: `pyproject.toml`, `insite/__init__.py`, `insite/modules.txt`, `insite/hooks.py`, `insite/patches.txt`, `README.md`, `license.txt`, `.gitignore`
- Create package dirs with `__init__.py`: `insite/calc/`, `insite/config/`, `insite/overrides/`, `insite/insite/`, `insite/tests/`

**Interfaces:**
- Produces: installable Frappe app package named `insite`, module `Insite`.

- [ ] **Step 1: Create the branch**

```bash
cd "<repo working copy>"
git checkout -b insite
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "insite"
authors = [{ name = "Inspect Solutions", email = "mina@inspect-solutions.com" }]
description = "Insite — configuration-driven contracting vertical for ERPNext"
requires-python = ">=3.10"
readme = "README.md"
dynamic = ["version"]
dependencies = []

[build-system]
requires = ["flit_core >=3.4,<4"]
build-backend = "flit_core.buildapi"

[tool.bench.frappe-dependencies]
frappe = ">=15.0.0,<17.0.0"
erpnext = ">=15.0.0,<17.0.0"
```

- [ ] **Step 3: Write `insite/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Write `insite/modules.txt`**

```
Insite
```

- [ ] **Step 5: Write `insite/hooks.py`** (minimal; extended in Tasks 13 & 16)

```python
app_name = "insite"
app_title = "Insite"
app_publisher = "Inspect Solutions"
app_description = "Configuration-driven contracting vertical for ERPNext"
app_email = "mina@inspect-solutions.com"
app_license = "MIT"

# Extended in later tasks:
after_install = "insite.install.after_install"
after_migrate = "insite.install.after_migrate"
```

- [ ] **Step 6: Write `insite/patches.txt`**

```
[pre_model_sync]

[post_model_sync]
insite.patches.v0_0_1.ensure_setup
```

- [ ] **Step 7: Create empty `__init__.py` in every package dir**

`insite/calc/__init__.py`, `insite/config/__init__.py`, `insite/overrides/__init__.py`, `insite/insite/__init__.py`, `insite/tests/__init__.py` — each an empty file.

- [ ] **Step 8: Write `README.md`, `license.txt` (MIT), `.gitignore`** (`__pycache__/`, `*.pyc`, `.DS_Store`).

- [ ] **Step 9: Validate & commit**

```bash
python -m py_compile insite/__init__.py insite/hooks.py
git add -A && git commit -m "feat: scaffold insite app skeleton on branch insite"
```

---

### Task 2: Pure measures engine (`calc/measures.py`)

**Files:**
- Create: `insite/calc/measures.py`
- Test: `insite/tests/test_measures.py`

**Interfaces:**
- Produces:
  - `MEASURE_KEYS: set[str]` = {"area","perimeter","linear","count","piece_waste","manual","formula"}
  - `compute(measure: str, *, height=0.0, width=0.0, length=0.0, count=1.0, wastage=1.0, formula=None) -> float | None` — returns billable qty; `None` for `manual`; raises `ValueError` for unknown measure; delegates `formula` to `evaluate_formula`.
  - `evaluate_formula(formula: str, tokens: dict) -> float` (implemented in Task 3).

- [ ] **Step 1: Write the failing test** — `insite/tests/test_measures.py`

```python
from insite.calc.measures import compute

def test_area():
    assert compute("area", height=1.5, width=2.8, count=40) == 168.0

def test_perimeter():
    assert compute("perimeter", height=1.5, width=2.8, count=40) == 344.0

def test_linear():
    assert compute("linear", length=3.0, count=60) == 180.0

def test_count_only():
    assert compute("count", count=12) == 12.0

def test_piece_waste():
    assert compute("piece_waste", count=500, wastage=1.1) == 550.0

def test_manual_returns_none():
    assert compute("manual", count=5) is None

def test_defaults_count_and_wastage_default_to_one():
    assert compute("area", height=2, width=3) == 6.0          # count defaults 1
    assert compute("piece_waste", count=10) == 10.0           # wastage defaults 1

def test_blank_inputs_coerced_to_zero():
    assert compute("area", height="", width=None, count=40) == 0.0

def test_unknown_measure_raises():
    import pytest
    with pytest.raises(ValueError):
        compute("nope", count=1)

if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except BaseException as e:  # noqa
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    sys.exit(1 if failed else 0)
```

- [ ] **Step 2: Run it — expect FAIL** (`ModuleNotFoundError: insite.calc.measures`)

Run: `python -m pytest insite/tests/test_measures.py -v`

- [ ] **Step 3: Implement `insite/calc/measures.py`**

```python
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
```

Note: `count`/`wastage` default to 1.0 when zero/blank (an unspecified count means one unit; unspecified wastage means no allowance). `evaluate_formula` is added in Task 3; the `formula` test lives there.

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest insite/tests/test_measures.py -v`

- [ ] **Step 5: Commit**

```bash
git add insite/calc/measures.py insite/tests/test_measures.py
git commit -m "feat: pure measurement engine (area/perimeter/linear/count/piece_waste)"
```

---

### Task 3: Plain-words formula evaluator (safe, offline)

**Files:**
- Modify: `insite/calc/measures.py` (add `evaluate_formula` + AST guard)
- Test: `insite/tests/test_formula.py`

**Interfaces:**
- Produces: `evaluate_formula(formula: str, tokens: dict) -> float` — evaluates a plain-words arithmetic expression over `tokens` (height/width/length/count/wastage) plus whitelisted math; raises `ValueError` on empty/invalid/unsafe input.

- [ ] **Step 1: Write the failing test** — `insite/tests/test_formula.py`

```python
import pytest
from insite.calc.measures import evaluate_formula, compute

T = {"height": 1.5, "width": 2.8, "length": 3.0, "count": 40.0, "wastage": 1.1}

def test_basic_arithmetic():
    assert evaluate_formula("height * width * count", T) == 168.0

def test_with_wastage_and_constant():
    assert evaluate_formula("height * width * count * 1.1", T) == pytest.approx(184.8)

def test_whitelisted_function():
    assert evaluate_formula("round(height * width, 2)", T) == 4.2

def test_via_compute_formula():
    assert compute("formula", height=1.5, width=2.8, count=40,
                   formula="height * width * count") == 168.0

def test_empty_formula_raises():
    with pytest.raises(ValueError):
        evaluate_formula("", T)

def test_unknown_name_raises():
    with pytest.raises(ValueError):
        evaluate_formula("height * price", T)

def test_attribute_access_blocked():
    with pytest.raises(ValueError):
        evaluate_formula("height.__class__", T)

def test_call_of_non_whitelisted_blocked():
    with pytest.raises(ValueError):
        evaluate_formula("__import__('os')", T)

if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except BaseException as e:  # noqa
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    sys.exit(1 if failed else 0)
```

- [ ] **Step 2: Run it — expect FAIL** (`ImportError: cannot import name 'evaluate_formula'`)

Run: `python -m pytest insite/tests/test_formula.py -v`

- [ ] **Step 3: Implement `evaluate_formula` in `insite/calc/measures.py`** (append)

```python
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
```

- [ ] **Step 4: Run tests — expect PASS** (both test files)

Run: `python -m pytest insite/tests/test_measures.py insite/tests/test_formula.py -v`

- [ ] **Step 5: Commit**

```bash
git add insite/calc/measures.py insite/tests/test_formula.py
git commit -m "feat: safe plain-words formula evaluator (AST-restricted)"
```

---

### Task 4: Pure rule resolution (`calc/resolve.py`)

**Files:**
- Create: `insite/calc/resolve.py`
- Test: `insite/tests/test_resolve.py`

**Interfaces:**
- Produces:
  - `SPECIFICITY: dict` mapping apply_on → score (`Item Code`:400, `Item Template`:300, `Item Attribute Value`:200, `Item Group`:100).
  - `rule_score(rule: dict, item: dict) -> int` — specificity if the rule matches `item`, else `-1`. `item` = {item_code, item_group, variant_of, has_variants, attributes: {attr: value}}.
  - `resolve_rule(item: dict, rules: list[dict]) -> dict | None` — most-specific-wins; `rules` pre-sorted by priority desc then recency; first at the top specificity wins.
- Rule dict shape: `{source, measure, formula, apply_on, item_code, item_template, item_group, item_attribute, attribute_value, priority}`.

- [ ] **Step 1: Write the failing test** — `insite/tests/test_resolve.py`

```python
from insite.calc.resolve import rule_score, resolve_rule

ITEM = {"item_code": "GLZ-DGU-6MM", "item_group": "Glazing",
        "variant_of": None, "has_variants": 0, "attributes": {}}

def r(**kw):
    base = {"source": "?", "measure": "area", "formula": None, "apply_on": "Item Group",
            "item_code": None, "item_template": None, "item_group": None,
            "item_attribute": None, "attribute_value": None, "priority": 0}
    base.update(kw); return base

def test_group_match():
    assert rule_score(r(apply_on="Item Group", item_group="Glazing"), ITEM) == 100

def test_group_nomatch():
    assert rule_score(r(apply_on="Item Group", item_group="Aluminium"), ITEM) == -1

def test_item_code_match_beats_group():
    rules = [r(source="grp", apply_on="Item Group", item_group="Glazing", priority=99),
             r(source="code", apply_on="Item Code", item_code="GLZ-DGU-6MM", priority=0)]
    assert resolve_rule(ITEM, rules)["source"] == "code"

def test_attribute_match():
    item = dict(ITEM, attributes={"Thickness": "6mm"})
    rule = r(apply_on="Item Attribute Value", item_attribute="Thickness", attribute_value="6mm")
    assert rule_score(rule, item) == 200

def test_no_match_returns_none():
    assert resolve_rule(ITEM, [r(apply_on="Item Group", item_group="Wood")]) is None

if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except BaseException as e:  # noqa
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    sys.exit(1 if failed else 0)
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest insite/tests/test_resolve.py -v`

- [ ] **Step 3: Implement `insite/calc/resolve.py`**

```python
"""Pure most-specific-wins rule resolution (framework-free, offline-testable)."""
from __future__ import annotations

SPECIFICITY = {"Item Code": 400, "Item Template": 300, "Item Attribute Value": 200, "Item Group": 100}


def rule_score(rule, item):
    a = rule.get("apply_on")
    if a == "Item Code":
        return SPECIFICITY[a] if rule.get("item_code") and rule["item_code"] == item.get("item_code") else -1
    if a == "Item Template":
        template = item.get("variant_of") or (item.get("item_code") if item.get("has_variants") else None)
        return SPECIFICITY[a] if rule.get("item_template") and rule["item_template"] == template else -1
    if a == "Item Attribute Value":
        if not rule.get("item_attribute"):
            return -1
        val = (item.get("attributes") or {}).get(rule["item_attribute"])
        return SPECIFICITY[a] if val is not None and str(val) == str(rule.get("attribute_value")) else -1
    if a == "Item Group":
        return SPECIFICITY[a] if rule.get("item_group") and rule["item_group"] == item.get("item_group") else -1
    return -1


def resolve_rule(item, rules):
    best, best_score = None, -1
    for rule in rules:  # pre-sorted priority desc, recency desc
        s = rule_score(rule, item)
        if s > best_score:
            best, best_score = rule, s
    return best
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest insite/tests/test_resolve.py -v`

- [ ] **Step 5: Commit**

```bash
git add insite/calc/resolve.py insite/tests/test_resolve.py
git commit -m "feat: pure most-specific-wins rule resolution"
```

---

### Task 5: Parity test against the legacy oracle

**Files:**
- Test: `insite/tests/test_parity.py`

**Interfaces:**
- Consumes: `insite.calc.measures.compute`.
- Produces: a locked table of (measure, inputs → expected qty) reproducing the legacy `contracting` engine's results; guards against regressions.

- [ ] **Step 1: Write the parity test** — `insite/tests/test_parity.py`

```python
from insite.calc.measures import compute

# Oracle: values verified against the legacy `contracting` engine + its 11 unit tests.
CASES = [
    ("area",        dict(height=1.5, width=2.8, count=40),           168.0),
    ("area",        dict(height=1.2, width=2.4, count=3),            8.64),
    ("perimeter",   dict(height=1.5, width=2.8, count=40),           344.0),
    ("linear",      dict(length=3.0, count=60),                      180.0),
    ("piece_waste", dict(count=500, wastage=1.1),                    550.0),
    ("count",       dict(count=25),                                  25.0),
    ("formula",     dict(height=1.5, width=2.8, count=40,
                         formula="height * width * count"),          168.0),
]

def test_parity_matches_oracle():
    for measure, kw, expected in CASES:
        got = compute(measure, **kw)
        assert abs(got - expected) < 1e-9, f"{measure} {kw}: {got} != {expected}"

if __name__ == "__main__":
    import sys
    try:
        test_parity_matches_oracle(); print("PASS parity"); sys.exit(0)
    except BaseException as e:  # noqa
        print("FAIL parity ->", repr(e)); sys.exit(1)
```

- [ ] **Step 2: Run it — expect PASS** (measures already implemented)

Run: `python -m pytest insite/tests/test_parity.py -v`

- [ ] **Step 3: Commit**

```bash
git add insite/tests/test_parity.py
git commit -m "test: parity of measures against legacy oracle"
```

---

### Task 6: Code-defined custom fields (`config/custom_fields.py`)

**Files:**
- Create: `insite/config/custom_fields.py`

**Interfaces:**
- Produces:
  - `ITEM_DOCTYPES: list[str]` (the 9 item child tables).
  - `get_custom_fields() -> dict` mapping each item doctype → the field list.
  - `ensure_custom_fields() -> None` — idempotent `create_custom_fields(..., ignore_validate=True)`.

- [ ] **Step 1: Write `insite/config/custom_fields.py`**

```python
"""Code-defined Custom Fields for ERPNext item child tables (idempotent).

Applied via create_custom_fields in after_install/after_migrate/patch — never
as fixtures, never via Export-Customizations. Fieldnames are stable and
app-owned; only labels are human/bilingual.
"""
from __future__ import annotations
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_DOCTYPES = [
    "Quotation Item", "Sales Order Item", "Delivery Note Item", "Sales Invoice Item",
    "Material Request Item", "Supplier Quotation Item", "Purchase Order Item",
    "Purchase Receipt Item", "Purchase Invoice Item",
]


def _fields():
    return [
        {"fieldname": "custom_insite_dim_sb", "label": "Insite — Measurements",
         "fieldtype": "Section Break", "insert_after": "uom", "collapsible": 1},
        {"fieldname": "custom_base_qty", "label": "Count", "fieldtype": "Float",
         "insert_after": "custom_insite_dim_sb",
         "description": "Number of units/pieces. Input to the measurement engine."},
        {"fieldname": "custom_height", "label": "Height", "fieldtype": "Float",
         "insert_after": "custom_base_qty"},
        {"fieldname": "custom_width", "label": "Width", "fieldtype": "Float",
         "insert_after": "custom_height"},
        {"fieldname": "custom_insite_dim_cb", "fieldtype": "Column Break",
         "insert_after": "custom_width"},
        {"fieldname": "custom_length", "label": "Length", "fieldtype": "Float",
         "insert_after": "custom_insite_dim_cb"},
        {"fieldname": "custom_waste_factor", "label": "Wastage", "fieldtype": "Float",
         "insert_after": "custom_length",
         "description": "Optional wastage allowance multiplier (defaults to 1)."},
        {"fieldname": "custom_insite_calc_sb", "label": "Insite — Calculated",
         "fieldtype": "Section Break", "insert_after": "custom_waste_factor", "collapsible": 1},
        {"fieldname": "custom_calculated_qty", "label": "Calculated Quantity",
         "fieldtype": "Float", "insert_after": "custom_insite_calc_sb",
         "read_only": 1, "no_copy": 1},
        {"fieldname": "custom_calc_measure", "label": "Measure Used", "fieldtype": "Data",
         "insert_after": "custom_calculated_qty", "read_only": 1, "no_copy": 1},
        {"fieldname": "custom_insite_calc_cb", "fieldtype": "Column Break",
         "insert_after": "custom_calc_measure"},
        {"fieldname": "custom_calc_source", "label": "Work Item Type", "fieldtype": "Data",
         "insert_after": "custom_insite_calc_cb", "read_only": 1, "no_copy": 1},
        {"fieldname": "custom_calc_dimensions", "label": "Calc Inputs (JSON)",
         "fieldtype": "Small Text", "insert_after": "custom_calc_source",
         "read_only": 1, "hidden": 1, "no_copy": 1},
    ]


def get_custom_fields():
    fields = _fields()
    return {dt: fields for dt in ITEM_DOCTYPES}


def ensure_custom_fields():
    create_custom_fields(get_custom_fields(), ignore_validate=True)
```

- [ ] **Step 2: Validate (compile)**

Run: `python -m py_compile insite/config/custom_fields.py`
Expected: no output (success). (Runtime needs a site; verified on-site in Task 18.)

- [ ] **Step 3: Commit**

```bash
git add insite/config/custom_fields.py
git commit -m "feat: code-defined dimension + audit custom fields"
```

---

### Task 7: Scope Item accounting dimension (`config/accounting_dimension.py`)

**Files:**
- Create: `insite/config/accounting_dimension.py`

**Interfaces:**
- Produces:
  - `DIMENSION_DOCTYPE = "Scope Item"`, `DIMENSION_FIELDNAME = "scope_item"`, `DIMENSION_LABEL = "Scope"`.
  - `ensure_scope_dimension() -> None` — idempotent create of the Accounting Dimension + post-create field-count guard (ERPNext #25485).

- [ ] **Step 1: Write `insite/config/accounting_dimension.py`**

```python
"""Create the 'Scope Item' Accounting Dimension (fieldname `scope_item`).

Guards ERPNext issue #25485 (partial dimension-field creation) by verifying the
`scope_item` column exists on the core sales/purchase item tables after create.
"""
from __future__ import annotations
import frappe

DIMENSION_DOCTYPE = "Scope Item"
DIMENSION_FIELDNAME = "scope_item"
DIMENSION_LABEL = "Scope"

_VERIFY_TABLES = ["Sales Order Item", "Delivery Note Item", "Sales Invoice Item",
                  "Purchase Order Item", "Purchase Receipt Item", "Purchase Invoice Item"]


def ensure_scope_dimension():
    if not frappe.db.exists("Accounting Dimension", DIMENSION_DOCTYPE):
        doc = frappe.new_doc("Accounting Dimension")
        doc.document_type = DIMENSION_DOCTYPE
        doc.label = DIMENSION_LABEL
        doc.fieldname = DIMENSION_FIELDNAME
        doc.insert(ignore_permissions=True)
    _verify_columns()


def _verify_columns():
    missing = []
    for dt in _VERIFY_TABLES:
        try:
            cols = frappe.db.get_table_columns(dt)
        except Exception:  # noqa: BLE001
            cols = []
        if DIMENSION_FIELDNAME not in cols:
            missing.append(dt)
    if missing:
        frappe.log_error(
            title="Insite: scope_item dimension missing columns",
            message="Missing on: " + ", ".join(missing) +
                    " — re-run migrate or re-save the Accounting Dimension.",
        )
```

- [ ] **Step 2: Validate (compile) & commit**

```bash
python -m py_compile insite/config/accounting_dimension.py
git add insite/config/accounting_dimension.py
git commit -m "feat: scope_item accounting dimension with field-count guard"
```

---

### Task 8: DocType — Work Item Type (+ child Measurement Rule, Insite Type Account)

**Files:**
- Create: `insite/insite/doctype/insite_type_account/insite_type_account.json`
- Create: `insite/insite/doctype/measurement_rule/measurement_rule.json`
- Create: `insite/insite/doctype/work_item_type/work_item_type.json`
- Create: `insite/insite/doctype/work_item_type/work_item_type.py`
- Create: `__init__.py` in each of the three doctype dirs
- Test: `insite/tests/test_work_item_type_json.py`

**Interfaces:**
- Produces: DocType `Work Item Type` (autoname `field:work_item_type_name`) with child tables `Measurement Rule` and `Insite Type Account`; controller `WorkItemType.validate` (formula sanity + measure required).

- [ ] **Step 1: Write `insite_type_account.json`** (istable=1)

```json
{
  "name": "Insite Type Account", "istable": 1, "editable_grid": 1,
  "field_order": ["company", "income_account", "expense_account", "cost_center"],
  "fields": [
    {"fieldname": "company", "fieldtype": "Link", "options": "Company", "label": "Company", "in_list_view": 1, "reqd": 1},
    {"fieldname": "income_account", "fieldtype": "Link", "options": "Account", "label": "Income Account", "in_list_view": 1},
    {"fieldname": "expense_account", "fieldtype": "Link", "options": "Account", "label": "Expense Account", "in_list_view": 1},
    {"fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "label": "Cost Center"}
  ],
  "permissions": []
}
```

- [ ] **Step 2: Write `measurement_rule.json`** (istable=1)

```json
{
  "name": "Measurement Rule", "istable": 1, "editable_grid": 1,
  "field_order": ["apply_on", "item_code", "item_group", "item_template",
                  "item_attribute", "attribute_value", "measure", "formula", "priority"],
  "fields": [
    {"fieldname": "apply_on", "fieldtype": "Select", "label": "Applies To",
     "options": "Item Group\nItem Code\nItem Template\nItem Attribute Value",
     "default": "Item Group", "in_list_view": 1, "reqd": 1},
    {"fieldname": "item_code", "fieldtype": "Link", "options": "Item", "label": "Item",
     "depends_on": "eval:doc.apply_on=='Item Code'"},
    {"fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "label": "Item Group",
     "depends_on": "eval:doc.apply_on=='Item Group'"},
    {"fieldname": "item_template", "fieldtype": "Link", "options": "Item", "label": "Item Template",
     "depends_on": "eval:doc.apply_on=='Item Template'"},
    {"fieldname": "item_attribute", "fieldtype": "Link", "options": "Item Attribute", "label": "Attribute",
     "depends_on": "eval:doc.apply_on=='Item Attribute Value'"},
    {"fieldname": "attribute_value", "fieldtype": "Data", "label": "Attribute Value",
     "depends_on": "eval:doc.apply_on=='Item Attribute Value'"},
    {"fieldname": "measure", "fieldtype": "Select", "label": "Measured By",
     "options": "area\nperimeter\nlinear\ncount\npiece_waste\nmanual\nformula",
     "default": "area", "in_list_view": 1, "reqd": 1},
    {"fieldname": "formula", "fieldtype": "Data", "label": "Formula",
     "depends_on": "eval:doc.measure=='formula'",
     "description": "Plain words: height, width, length, count, wastage (+ abs round min max pow sqrt ceil floor, pi)."},
    {"fieldname": "priority", "fieldtype": "Int", "label": "Priority", "default": "0", "in_list_view": 1}
  ],
  "permissions": []
}
```

Note: `measure` is a Select of stable keys; the client script (Task 14) shows friendly labels ("Area (H×W×Count)"). The `formula` field uses plain words with the chips helper in Task 14.

- [ ] **Step 3: Write `work_item_type.json`** (autoname `field:work_item_type_name`)

```json
{
  "name": "Work Item Type", "autoname": "field:work_item_type_name",
  "allow_rename": 1, "track_changes": 1,
  "field_order": ["work_item_type_name", "disabled", "column_break_head",
                  "tolerance_percentage", "description",
                  "rules_section", "measurement_rules",
                  "accounts_section", "accounts"],
  "fields": [
    {"fieldname": "work_item_type_name", "fieldtype": "Data", "label": "Work Item Type",
     "reqd": 1, "unique": 1, "in_list_view": 1},
    {"fieldname": "disabled", "fieldtype": "Check", "label": "Disabled"},
    {"fieldname": "column_break_head", "fieldtype": "Column Break"},
    {"fieldname": "tolerance_percentage", "fieldtype": "Percent", "label": "Tolerance %"},
    {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
    {"fieldname": "rules_section", "fieldtype": "Section Break", "label": "How is this measured?"},
    {"fieldname": "measurement_rules", "fieldtype": "Table", "options": "Measurement Rule",
     "label": "Measurement Rules"},
    {"fieldname": "accounts_section", "fieldtype": "Section Break", "label": "Default Accounts (per company)"},
    {"fieldname": "accounts", "fieldtype": "Table", "options": "Insite Type Account", "label": "Accounts"}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1},
    {"role": "Contracting Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1}
  ]
}
```

- [ ] **Step 4: Write `work_item_type.py`**

```python
"""Work Item Type controller: validate measurement rules."""
from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document
from insite.calc.measures import MEASURE_KEYS, evaluate_formula

_SAMPLE = {"height": 1.0, "width": 1.0, "length": 1.0, "count": 1.0, "wastage": 1.0}


class WorkItemType(Document):
    def validate(self):
        for row in (self.measurement_rules or []):
            if row.measure not in MEASURE_KEYS:
                frappe.throw(_("Row {0}: unknown measure {1}").format(row.idx, row.measure))
            if row.measure == "formula":
                if not (row.formula or "").strip():
                    frappe.throw(_("Row {0}: choose a formula or a ready-made measure.").format(row.idx))
                try:
                    evaluate_formula(row.formula, _SAMPLE)
                except Exception as e:  # noqa: BLE001
                    frappe.throw(_("Row {0}: invalid formula — {1}").format(row.idx, str(e)))
            self._validate_scope(row)

    def _validate_scope(self, row):
        need = {"Item Code": "item_code", "Item Template": "item_template",
                "Item Group": "item_group", "Item Attribute Value": "item_attribute"}.get(row.apply_on)
        if need and not row.get(need):
            frappe.throw(_("Row {0}: choose what '{1}' applies to.").format(row.idx, row.apply_on))
```

- [ ] **Step 5: Write the JSON validity test** — `insite/tests/test_work_item_type_json.py`

```python
import json, glob, os

def test_all_insite_doctype_json_parse():
    files = glob.glob("insite/insite/doctype/**/*.json", recursive=True)
    assert files, "no doctype json found"
    for f in files:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        assert d.get("name"), f"{f} missing name"

if __name__ == "__main__":
    import sys
    try:
        test_all_insite_doctype_json_parse(); print("PASS json"); sys.exit(0)
    except BaseException as e:  # noqa
        print("FAIL ->", repr(e)); sys.exit(1)
```

- [ ] **Step 6: Add `__init__.py`** (empty) to `work_item_type/`, `measurement_rule/`, `insite_type_account/`.

- [ ] **Step 7: Validate & commit**

```bash
python -m py_compile insite/insite/doctype/work_item_type/work_item_type.py
python -m pytest insite/tests/test_work_item_type_json.py -v
git add insite/insite/doctype/work_item_type insite/insite/doctype/measurement_rule insite/insite/doctype/insite_type_account insite/tests/test_work_item_type_json.py
git commit -m "feat: Work Item Type doctype with Measurement Rules + accounts"
```

---

### Task 9: DocType — Scope Item

**Files:**
- Create: `insite/insite/doctype/scope_item/scope_item.json`
- Create: `insite/insite/doctype/scope_item/scope_item.py`
- Create: `insite/insite/doctype/scope_item/__init__.py`

**Interfaces:**
- Produces: DocType `Scope Item` (autoname `SC-.YYYY.-`), Project-anchored, with read-only `net_variations_amount`, `revised_planned_amount`; controller method `recompute_revised()` (called by Variation Order in Task 10).

- [ ] **Step 1: Write `scope_item.json`**

```json
{
  "name": "Scope Item", "autoname": "naming_series:", "allow_rename": 0, "track_changes": 1,
  "field_order": ["naming_series", "scope_title", "status", "disabled", "column_break_head",
                  "project", "customer", "company", "currency",
                  "scope_section", "scope_description",
                  "planning_section", "original_planned_amount", "original_planned_qty", "uom",
                  "column_break_plan", "net_variations_amount", "revised_planned_amount"],
  "fields": [
    {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series", "options": "SC-.YYYY.-", "default": "SC-.YYYY.-", "hidden": 1},
    {"fieldname": "scope_title", "fieldtype": "Data", "label": "Title", "reqd": 1, "in_list_view": 1},
    {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Draft\nActive\nOn Hold\nCompleted\nCancelled", "default": "Draft", "in_standard_filter": 1, "in_list_view": 1},
    {"fieldname": "disabled", "fieldtype": "Check", "label": "Disabled", "description": "Hides this scope from Accounting Dimension pickers."},
    {"fieldname": "column_break_head", "fieldtype": "Column Break"},
    {"fieldname": "project", "fieldtype": "Link", "options": "Project", "label": "Project", "reqd": 1, "in_standard_filter": 1},
    {"fieldname": "customer", "fieldtype": "Link", "options": "Customer", "label": "Customer", "fetch_from": "project.customer", "read_only": 1},
    {"fieldname": "company", "fieldtype": "Link", "options": "Company", "label": "Company", "fetch_from": "project.company", "read_only": 1},
    {"fieldname": "currency", "fieldtype": "Link", "options": "Currency", "label": "Currency"},
    {"fieldname": "scope_section", "fieldtype": "Section Break", "label": "Scope of Work"},
    {"fieldname": "scope_description", "fieldtype": "Text Editor", "label": "Scope Description"},
    {"fieldname": "planning_section", "fieldtype": "Section Break", "label": "Planned Values"},
    {"fieldname": "original_planned_amount", "fieldtype": "Currency", "label": "Planned Amount", "options": "currency"},
    {"fieldname": "original_planned_qty", "fieldtype": "Float", "label": "Planned Qty"},
    {"fieldname": "uom", "fieldtype": "Link", "options": "UOM", "label": "UOM"},
    {"fieldname": "column_break_plan", "fieldtype": "Column Break"},
    {"fieldname": "net_variations_amount", "fieldtype": "Currency", "label": "Net Variations", "options": "currency", "read_only": 1},
    {"fieldname": "revised_planned_amount", "fieldtype": "Currency", "label": "Revised Amount", "options": "currency", "read_only": 1}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1},
    {"role": "Contracting Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1},
    {"role": "Accounts User", "read": 1, "report": 1},
    {"role": "Sales User", "read": 1, "report": 1}
  ]
}
```

- [ ] **Step 2: Write `scope_item.py`**

```python
"""Scope Item controller. Revised = Original + Σ approved Variation deltas.

`recompute_revised()` is idempotent and called by Variation Order on submit/cancel
(documented save path, never db_set)."""
from __future__ import annotations
import frappe
from frappe.utils import flt
from frappe.model.document import Document


class ScopeItem(Document):
    def validate(self):
        self._apply_revised(save=False)

    def recompute_revised(self):
        """Recompute net variations + revised from submitted Variation Lines, then save."""
        self._apply_revised(save=False)
        self.save(ignore_permissions=True)

    def _apply_revised(self, save=False):
        net = frappe.db.sql(
            """
            select coalesce(sum(vl.delta_amount), 0)
            from `tabVariation Line` vl
            join `tabVariation Order` vo on vl.parent = vo.name
            where vl.scope_item = %s and vo.docstatus = 1
            """,
            (self.name,),
        )[0][0]
        self.net_variations_amount = flt(net)
        self.revised_planned_amount = flt(self.original_planned_amount) + flt(net)
```

Note: a brand-new (unsaved) Scope Item has no `name` yet; the SQL simply returns 0 then, which is correct (no variations against an uncreated scope).

- [ ] **Step 3: Add `__init__.py`, validate & commit**

```bash
python -m py_compile insite/insite/doctype/scope_item/scope_item.py
python -m pytest insite/tests/test_work_item_type_json.py -v   # re-parses all doctype json
git add insite/insite/doctype/scope_item
git commit -m "feat: Scope Item doctype (project-anchored, revised amount)"
```

---

### Task 10: DocType — Variation Order (+ child Variation Line)

**Files:**
- Create: `insite/insite/doctype/variation_line/variation_line.json` (+ `__init__.py`)
- Create: `insite/insite/doctype/variation_order/variation_order.json` (+ `__init__.py`)
- Create: `insite/insite/doctype/variation_order/variation_order.py`

**Interfaces:**
- Consumes: `ScopeItem.recompute_revised()` (Task 9).
- Produces: submittable DocType `Variation Order` (autoname `VO-.YYYY.-`) whose `on_submit`/`on_cancel` recompute each referenced Scope Item.

- [ ] **Step 1: Write `variation_line.json`** (istable=1)

```json
{
  "name": "Variation Line", "istable": 1, "editable_grid": 1,
  "field_order": ["scope_item", "change_type", "delta_qty", "delta_amount", "note"],
  "fields": [
    {"fieldname": "scope_item", "fieldtype": "Link", "options": "Scope Item", "label": "Scope", "reqd": 1, "in_list_view": 1},
    {"fieldname": "change_type", "fieldtype": "Select", "options": "Add\nOmit\nModify", "default": "Add", "label": "Type", "in_list_view": 1},
    {"fieldname": "delta_qty", "fieldtype": "Float", "label": "Qty Change", "in_list_view": 1},
    {"fieldname": "delta_amount", "fieldtype": "Currency", "label": "Amount Change", "in_list_view": 1},
    {"fieldname": "note", "fieldtype": "Data", "label": "Note"}
  ],
  "permissions": []
}
```

Note: for `Omit`, the user enters a negative `delta_amount` (a helper hint is shown by the client script in Task 14).

- [ ] **Step 2: Write `variation_order.json`** (is_submittable=1, autoname series)

```json
{
  "name": "Variation Order", "autoname": "naming_series:", "is_submittable": 1, "track_changes": 1,
  "field_order": ["naming_series", "project", "date", "column_break_head", "customer", "reason",
                  "lines_section", "variation_lines", "description", "amended_from"],
  "fields": [
    {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series", "options": "VO-.YYYY.-", "default": "VO-.YYYY.-", "hidden": 1},
    {"fieldname": "project", "fieldtype": "Link", "options": "Project", "label": "Project", "reqd": 1, "in_standard_filter": 1},
    {"fieldname": "date", "fieldtype": "Date", "label": "Date", "default": "Today", "reqd": 1},
    {"fieldname": "column_break_head", "fieldtype": "Column Break"},
    {"fieldname": "customer", "fieldtype": "Link", "options": "Customer", "label": "Customer", "fetch_from": "project.customer", "read_only": 1},
    {"fieldname": "reason", "fieldtype": "Data", "label": "Reason"},
    {"fieldname": "lines_section", "fieldtype": "Section Break", "label": "Scope Changes"},
    {"fieldname": "variation_lines", "fieldtype": "Table", "options": "Variation Line", "label": "Variation Lines", "reqd": 1},
    {"fieldname": "description", "fieldtype": "Text", "label": "Description"},
    {"fieldname": "amended_from", "fieldtype": "Link", "options": "Variation Order", "label": "Amended From", "read_only": 1, "no_copy": 1, "print_hide": 1}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1},
    {"role": "Contracting Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1}
  ]
}
```

- [ ] **Step 3: Write `variation_order.py`**

```python
"""Variation Order controller. On submit/cancel, recompute affected Scope Items."""
from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document


class VariationOrder(Document):
    def validate(self):
        for row in (self.variation_lines or []):
            if not row.scope_item:
                frappe.throw(_("Row {0}: choose a Scope.").format(row.idx))

    def on_submit(self):
        self._recompute_scopes()

    def on_cancel(self):
        self._recompute_scopes()

    def _recompute_scopes(self):
        names = {r.scope_item for r in (self.variation_lines or []) if r.scope_item}
        for name in names:
            frappe.get_doc("Scope Item", name).recompute_revised()
```

- [ ] **Step 4: Add `__init__.py` files, validate & commit**

```bash
python -m py_compile insite/insite/doctype/variation_order/variation_order.py
python -m pytest insite/tests/test_work_item_type_json.py -v
git add insite/insite/doctype/variation_order insite/insite/doctype/variation_line
git commit -m "feat: Variation Order (submittable) recomputing scope revised amounts"
```

---

### Task 11: DocType — Contracting Settings (single) + Contracting Price Role + price visibility

**Files:**
- Create: `insite/insite/doctype/contracting_price_role/contracting_price_role.json` (+ `__init__.py`)
- Create: `insite/insite/doctype/contracting_settings/contracting_settings.json` (+ `__init__.py`)
- Create: `insite/insite/doctype/contracting_settings/contracting_settings.py`
- Create: `insite/config/price_visibility.py`

**Interfaces:**
- Produces: single DocType `Contracting Settings`; `insite.config.price_visibility.apply_from_settings()` (no-op stub that is safe to call; full permlevel logic deferred — see note).

- [ ] **Step 1: Write `contracting_price_role.json`** (istable=1)

```json
{
  "name": "Contracting Price Role", "istable": 1, "editable_grid": 1,
  "field_order": ["role"],
  "fields": [{"fieldname": "role", "fieldtype": "Link", "options": "Role", "label": "Role", "in_list_view": 1, "reqd": 1}],
  "permissions": []
}
```

- [ ] **Step 2: Write `contracting_settings.json`** (issingle=1)

```json
{
  "name": "Contracting Settings", "issingle": 1,
  "field_order": ["price_visibility_section", "enable_price_visibility", "price_visibility_roles",
                  "calc_section", "default_tolerance_percentage"],
  "fields": [
    {"fieldname": "price_visibility_section", "fieldtype": "Section Break", "label": "Role-Based Price Visibility"},
    {"fieldname": "enable_price_visibility", "fieldtype": "Check", "label": "Enable Role-Based Price Visibility", "default": "0", "description": "Restricts selling price/amount visibility to the roles below (applied on save)."},
    {"fieldname": "price_visibility_roles", "fieldtype": "Table", "options": "Contracting Price Role", "label": "Price-Visible Roles", "depends_on": "enable_price_visibility"},
    {"fieldname": "calc_section", "fieldtype": "Section Break", "label": "Defaults"},
    {"fieldname": "default_tolerance_percentage", "fieldtype": "Percent", "label": "Default Tolerance %", "default": "0", "description": "Fallback tolerance when a Work Item Type does not set one."}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "print": 1, "email": 1, "share": 1},
    {"role": "Contracting Manager", "read": 1, "write": 1}
  ]
}
```

- [ ] **Step 3: Write `contracting_settings.py`**

```python
from __future__ import annotations
from frappe.model.document import Document


class ContractingSettings(Document):
    def on_update(self):
        from insite.config.price_visibility import apply_from_settings
        apply_from_settings()
```

- [ ] **Step 4: Write `insite/config/price_visibility.py`**

```python
"""Role-based price visibility.

v1: a safe, idempotent stub that reads the setting and does nothing when
disabled. The full permlevel-raise implementation is intentionally deferred
(it is not on the delivery-spine critical path) but the hook is wired so the
setting exists and can be turned on later without a schema change.
"""
from __future__ import annotations
import frappe


def apply_from_settings():
    settings = frappe.get_single("Contracting Settings")
    if not settings.enable_price_visibility:
        return
    # Deferred: raise permlevel on selling price/amount fields for the listed roles.
    frappe.logger("insite").info("price visibility enabled; permlevel application deferred to a later phase")
```

- [ ] **Step 5: Add `__init__.py`, validate & commit**

```bash
python -m py_compile insite/insite/doctype/contracting_settings/contracting_settings.py insite/config/price_visibility.py
python -m pytest insite/tests/test_work_item_type_json.py -v
git add insite/insite/doctype/contracting_settings insite/insite/doctype/contracting_price_role insite/config/price_visibility.py
git commit -m "feat: Contracting Settings single + price-visibility hook (stub)"
```

---

### Task 12: Engine glue (`calc/engine.py`)

**Files:**
- Create: `insite/calc/engine.py`

**Interfaces:**
- Consumes: `insite.calc.resolve.resolve_rule`, `insite.calc.measures.compute`.
- Produces:
  - `load_rules() -> list[dict]` — flatten enabled Work Item Types' Measurement Rules into resolver rule dicts (sorted priority desc, modified desc).
  - `has_rules() -> bool`
  - `_item_meta(item_code) -> dict|None`, `_attr_getter()` — Frappe lookups.
  - `compute_qty_for_row(row, rule) -> tuple[float|None, dict]`
  - `apply_rule_to_row(row, rule) -> None` — writes qty + audit fields.
  - `recalculate_document(doc) -> int`

- [ ] **Step 1: Write `insite/calc/engine.py`**

```python
"""Frappe glue around the pure calc core: load rules, resolve, apply to rows."""
from __future__ import annotations
import json
import frappe
from frappe.utils import cint, flt
from insite.calc import measures
from insite.calc.resolve import resolve_rule

_TARGET_FIELD = "qty"
_PRECISION = 3


def has_rules():
    return bool(frappe.get_all("Work Item Type", filters={"disabled": 0}, limit=1))


def load_rules():
    rules = []
    types = frappe.get_all("Work Item Type", filters={"disabled": 0}, fields=["name", "modified"],
                           order_by="modified desc")
    for t in types:
        doc = frappe.get_cached_doc("Work Item Type", t.name)
        for row in doc.measurement_rules:
            rules.append({
                "source": doc.name, "measure": row.measure, "formula": row.formula,
                "apply_on": row.apply_on, "item_code": row.item_code,
                "item_template": row.item_template, "item_group": row.item_group,
                "item_attribute": row.item_attribute, "attribute_value": row.attribute_value,
                "priority": cint(row.priority),
            })
    rules.sort(key=lambda r: r["priority"], reverse=True)  # stable; types already modified-desc
    return rules


def _item_meta(item_code):
    if not item_code:
        return None
    v = frappe.get_cached_value("Item", item_code,
                                ["item_group", "variant_of", "has_variants"], as_dict=True)
    return dict(v) if v else None


def _make_attr_getter():
    cache = {}
    def getter(item_code):
        if item_code not in cache:
            rows = frappe.get_all("Item Variant Attribute", filters={"parent": item_code},
                                  fields=["attribute", "attribute_value"])
            cache[item_code] = {r.attribute: r.attribute_value for r in rows}
        return cache[item_code]
    return getter


def _tokens(row):
    return {
        "height": flt(row.get("custom_height")),
        "width": flt(row.get("custom_width")),
        "length": flt(row.get("custom_length")),
        "count": flt(row.get("custom_base_qty")),
        "wastage": flt(row.get("custom_waste_factor")),
    }


def compute_qty_for_row(row, rule):
    tok = _tokens(row)
    qty = measures.compute(rule["measure"], formula=rule.get("formula"), **tok)
    return qty, tok


def apply_rule_to_row(row, rule):
    qty, tok = compute_qty_for_row(row, rule)
    row.set("custom_calc_measure", rule["measure"])
    row.set("custom_calc_source", rule["source"])
    row.set("custom_calc_dimensions", json.dumps(tok))
    if qty is None:  # manual
        return
    qty = flt(qty, _PRECISION)
    row.set(_TARGET_FIELD, qty)
    row.set("custom_calculated_qty", qty)


def recalculate_document(doc):
    items = doc.get("items")
    if not items or not has_rules():
        return 0
    rules = load_rules()
    if not rules:
        return 0
    attr_getter = _make_attr_getter()
    affected = 0
    for row in items:
        if not row.get("item_code"):
            continue
        meta = _item_meta(row.item_code)
        if not meta:
            continue
        item = {"item_code": row.item_code, "item_group": meta.get("item_group"),
                "variant_of": meta.get("variant_of"), "has_variants": meta.get("has_variants"),
                "attributes": attr_getter(row.item_code)}
        rule = resolve_rule(item, rules)
        if rule:
            apply_rule_to_row(row, rule)
            affected += 1
    return affected
```

- [ ] **Step 2: Validate (compile) & commit**

```bash
python -m py_compile insite/calc/engine.py
git add insite/calc/engine.py
git commit -m "feat: engine glue — load rules from Work Item Types, resolve & apply"
```

---

### Task 13: Transaction overrides + hooks wiring

**Files:**
- Create: `insite/overrides/transaction.py`
- Modify: `insite/hooks.py` (add `doc_events`, `doctype_js`)

**Interfaces:**
- Consumes: `insite.calc.engine.recalculate_document`.
- Produces: `recalculate(doc, method=None)` and `enforce_project_scope(doc, method=None)`; hooks wiring for the sell cycle (+ light purchase tagging support).

- [ ] **Step 1: Write `insite/overrides/transaction.py`**

```python
"""doc_events for sales/purchase transactions."""
from __future__ import annotations
import frappe
from frappe import _
from insite.calc import engine

_SELL = {"Quotation", "Sales Order", "Delivery Note", "Sales Invoice"}
_ENFORCE = {"Sales Order", "Delivery Note", "Sales Invoice"}  # not Quotation (early stage)


def recalculate(doc, method=None):
    try:
        engine.recalculate_document(doc)
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(title="Insite: calc engine error", message=frappe.get_traceback())
        raise


def enforce_project_scope(doc, method=None):
    """A Sales Order (and downstream) needs a Project + a Scope on every line."""
    if doc.doctype not in _ENFORCE:
        return
    if not doc.get("project"):
        frappe.throw(_("Add a Project before saving this {0}.").format(_(doc.doctype)))
    for row in (doc.get("items") or []):
        if not row.get("scope_item"):
            frappe.throw(_("Row {0}: choose a Scope.").format(row.idx))
```

- [ ] **Step 2: Extend `insite/hooks.py`** (append)

```python
# --- Transaction JS ---------------------------------------------------------
_INSITE_TXNS = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice",
                "Material Request", "Supplier Quotation", "Purchase Order",
                "Purchase Receipt", "Purchase Invoice"]

doctype_js = {dt: "public/js/insite_transaction.js" for dt in _INSITE_TXNS}
doctype_js["Work Item Type"] = "public/js/work_item_type.js"

# --- Document Events (server-authoritative) --------------------------------
doc_events = {dt: {"before_validate": "insite.overrides.transaction.recalculate"} for dt in _INSITE_TXNS}
for _dt in ["Sales Order", "Delivery Note", "Sales Invoice"]:
    doc_events[_dt]["validate"] = "insite.overrides.transaction.enforce_project_scope"

fixtures = []
```

- [ ] **Step 3: Validate (compile) & commit**

```bash
python -m py_compile insite/overrides/transaction.py insite/hooks.py
git add insite/overrides/transaction.py insite/hooks.py
git commit -m "feat: before_validate recompute + Project/Scope enforcement wiring"
```

---

### Task 14: Client scripts (measurement UX + dimension visibility)

**Files:**
- Create: `insite/public/js/work_item_type.js`
- Create: `insite/public/js/insite_transaction.js`

**Interfaces:**
- Produces: a "Test measure" button on Work Item Type; friendly measure labels + formula chips hints in the child grid; dimension-field visibility on transaction lines.

- [ ] **Step 1: Write `insite/public/js/work_item_type.js`**

```javascript
frappe.ui.form.on("Work Item Type", {
  refresh(frm) {
    frm.add_custom_button(__("Test a Measure"), () => test_measure_dialog());
  },
});

function test_measure_dialog() {
  const d = new frappe.ui.Dialog({
    title: __("Test a Measure"),
    fields: [
      {fieldname: "measure", label: __("Measured By"), fieldtype: "Select",
       options: "area\nperimeter\nlinear\ncount\npiece_waste\nformula", default: "area"},
      {fieldname: "formula", label: __("Formula (plain words)"), fieldtype: "Data",
       depends_on: "eval:doc.measure=='formula'",
       description: __("Words: height, width, length, count, wastage")},
      {fieldname: "height", label: "Height", fieldtype: "Float"},
      {fieldname: "width", label: "Width", fieldtype: "Float"},
      {fieldname: "length", label: "Length", fieldtype: "Float"},
      {fieldname: "count", label: __("Count"), fieldtype: "Float", default: 1},
      {fieldname: "wastage", label: __("Wastage"), fieldtype: "Float", default: 1},
    ],
    primary_action_label: __("Compute"),
    primary_action(v) {
      frappe.call({
        method: "insite.api.test_measure",
        args: v,
        callback: (r) => frappe.msgprint(__("Result: {0}", [r.message])),
      });
    },
  });
  d.show();
}
```

- [ ] **Step 2: Add the whitelisted API `insite/api.py`**

```python
import frappe
from insite.calc.measures import compute


@frappe.whitelist()
def test_measure(measure, height=0, width=0, length=0, count=1, wastage=1, formula=None):
    frappe.only_for(["Contracting Manager", "System Manager"])
    qty = compute(measure, height=height, width=width, length=length,
                  count=count, wastage=wastage, formula=formula)
    return qty
```

- [ ] **Step 3: Write `insite/public/js/insite_transaction.js`**

```javascript
// Show the Insite dimension fields on item rows; recompute is server-side.
const INSITE_DIMS = ["custom_base_qty", "custom_height", "custom_width",
                     "custom_length", "custom_waste_factor"];

frappe.ui.form.on("Sales Order Item", {
  items_add(frm, cdt, cdn) {},
});

// Nudge users: after editing a dimension, save to recompute (server-authoritative).
function insite_mark_dirty(frm) { frm.dirty(); }
```

Note: the visibility toggles are cosmetic; the authoritative recompute is the `before_validate` hook. Keep this script intentionally thin (the spec forbids client-side calc as source of truth).

- [ ] **Step 4: Validate (compile api) & commit**

```bash
python -m py_compile insite/api.py
git add insite/public/js/work_item_type.js insite/public/js/insite_transaction.js insite/api.py
git commit -m "feat: measurement Test button + whitelisted test_measure API + line JS"
```

---

### Task 15: Report — Contract Progress

**Files:**
- Create: `insite/insite/report/contract_progress/contract_progress.json`
- Create: `insite/insite/report/contract_progress/contract_progress.py`
- Create: `insite/insite/report/contract_progress/contract_progress.js`
- Create: `insite/insite/report/contract_progress/__init__.py`

**Interfaces:**
- Produces: Script Report "Contract Progress" (ref doctype Scope Item) with columns Scope · Title · Status · Planned · Net Variations · Revised · Ordered · Delivered · Invoiced · Variance · % Invoiced · Over-run.

- [ ] **Step 1: Write `contract_progress.json`**

```json
{
  "name": "Contract Progress", "doctype": "Report", "report_type": "Script Report",
  "ref_doctype": "Scope Item", "module": "Insite", "is_standard": "Yes", "disabled": 0,
  "roles": [{"role": "Contracting Manager"}, {"role": "Accounts User"}, {"role": "Sales User"}]
}
```

- [ ] **Step 2: Write `contract_progress.py`**

```python
"""Contract Progress — planned/ordered/delivered/invoiced per Scope Item."""
import frappe
from frappe import _
from frappe.utils import flt

FIELD = "scope_item"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Scope"), "fieldname": "scope", "fieldtype": "Link", "options": "Scope Item", "width": 140},
        {"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 200},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 80},
        {"label": _("Planned"), "fieldname": "planned", "fieldtype": "Currency", "width": 110},
        {"label": _("Net Variations"), "fieldname": "net_variations", "fieldtype": "Currency", "width": 110},
        {"label": _("Revised"), "fieldname": "revised", "fieldtype": "Currency", "width": 110},
        {"label": _("Ordered"), "fieldname": "ordered", "fieldtype": "Currency", "width": 110},
        {"label": _("Delivered"), "fieldname": "delivered", "fieldtype": "Currency", "width": 110},
        {"label": _("Invoiced"), "fieldname": "invoiced", "fieldtype": "Currency", "width": 110},
        {"label": _("Variance (Revised − Invoiced)"), "fieldname": "variance", "fieldtype": "Currency", "width": 150},
        {"label": _("% Invoiced"), "fieldname": "pct_invoiced", "fieldtype": "Percent", "width": 90},
        {"label": _("Over-run"), "fieldname": "overrun", "fieldtype": "Data", "width": 80},
    ]


def _sum_by_scope(child_dt, parent_dt, company=None):
    conditions = ["p.docstatus = 1", f"c.`{FIELD}` is not null", f"c.`{FIELD}` != ''"]
    params = {}
    if company:
        conditions.append("p.company = %(company)s")
        params["company"] = company
    try:
        rows = frappe.db.sql(
            f"""select c.`{FIELD}` as scope, sum(c.amount) as amt
                from `tab{child_dt}` c join `tab{parent_dt}` p on c.parent = p.name
                where {' and '.join(conditions)} group by c.`{FIELD}`""",
            params, as_dict=True)
        return {r.scope: flt(r.amt) for r in rows}
    except Exception:  # noqa: BLE001
        return {}


def get_data(filters):
    scope_filters = {}
    if filters.get("status"):
        scope_filters["status"] = filters.status
    if filters.get("project"):
        scope_filters["project"] = filters.project
    scopes = frappe.get_all("Scope Item", filters=scope_filters,
                            fields=["name", "scope_title", "status", "original_planned_amount",
                                    "net_variations_amount", "revised_planned_amount"],
                            order_by="name asc")
    ordered = _sum_by_scope("Sales Order Item", "Sales Order", filters.get("company"))
    delivered = _sum_by_scope("Delivery Note Item", "Delivery Note", filters.get("company"))
    invoiced = _sum_by_scope("Sales Invoice Item", "Sales Invoice", filters.get("company"))
    data = []
    for s in scopes:
        revised = flt(s.revised_planned_amount) or flt(s.original_planned_amount)
        o, d, i = flt(ordered.get(s.name)), flt(delivered.get(s.name)), flt(invoiced.get(s.name))
        data.append({
            "scope": s.name, "title": s.scope_title, "status": s.status,
            "planned": flt(s.original_planned_amount), "net_variations": flt(s.net_variations_amount),
            "revised": revised, "ordered": o, "delivered": d, "invoiced": i,
            "variance": revised - i,
            "pct_invoiced": (i / revised * 100.0) if revised else 0.0,
            "overrun": _("Yes") if max(o, d, i) > revised and revised else "",
        })
    return data
```

- [ ] **Step 3: Write `contract_progress.js`**

```javascript
frappe.query_reports["Contract Progress"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company"},
    {fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project"},
    {fieldname: "status", label: __("Status"), fieldtype: "Select",
     options: "\nDraft\nActive\nOn Hold\nCompleted\nCancelled"},
  ],
};
```

- [ ] **Step 4: Add `__init__.py`, validate & commit**

```bash
python -m py_compile insite/insite/report/contract_progress/contract_progress.py
python -m pytest insite/tests/test_work_item_type_json.py -v
git add insite/insite/report/contract_progress
git commit -m "feat: Contract Progress report"
```

---

### Task 16: Install / patches / roles

**Files:**
- Create: `insite/install.py`
- Create: `insite/patches/__init__.py`, `insite/patches/v0_0_1/__init__.py`, `insite/patches/v0_0_1/ensure_setup.py`

**Interfaces:**
- Consumes: `ensure_custom_fields`, `ensure_scope_dimension`, `apply_from_settings`.
- Produces: `after_install()`, `after_migrate()`, `create_roles()`, `ensure_settings_singleton()`; patch `ensure_setup.execute()`.

- [ ] **Step 1: Write `insite/install.py`**

```python
"""Idempotent install/migrate setup for Insite. No db_set; documented APIs only."""
from __future__ import annotations
import frappe
from insite.config.custom_fields import ensure_custom_fields
from insite.config.accounting_dimension import ensure_scope_dimension

ROLES = [
    ("Contracting Manager", "Full access to Work Item Types, Scopes, and Variation Orders."),
]


def after_install():
    _setup()


def after_migrate():
    _setup()


def _setup():
    create_roles()
    ensure_custom_fields()
    ensure_settings_singleton()
    ensure_scope_dimension()
    try:
        from insite.config.price_visibility import apply_from_settings
        apply_from_settings()
    except Exception:  # noqa: BLE001
        frappe.log_error(title="Insite: price visibility setup skipped", message=frappe.get_traceback())


def create_roles():
    for role_name, desc in ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name,
                            "desk_access": 1, "description": desc}).insert(ignore_permissions=True)


def ensure_settings_singleton():
    if not frappe.db.exists("Contracting Settings", "Contracting Settings"):
        frappe.get_single("Contracting Settings").save(ignore_permissions=True)
```

- [ ] **Step 2: Write `insite/patches/v0_0_1/ensure_setup.py`**

```python
from insite.install import _setup


def execute():
    _setup()
```

- [ ] **Step 3: Add `__init__.py` files, validate & commit**

```bash
python -m py_compile insite/install.py insite/patches/v0_0_1/ensure_setup.py
git add insite/install.py insite/patches
git commit -m "feat: idempotent install/migrate setup + roles + patch"
```

---

### Task 17: Workspace + docs + Arabic translations

**Files:**
- Create: `insite/insite/workspace/insite/insite.json`
- Create: `insite/locale/ar.po`
- Create: `docs/SETUP.md`, `docs/CONCEPTS.md`
- Modify: `README.md`

**Interfaces:**
- Produces: an "Insite" workspace with shortcuts (Work Item Type, Scope Item, Variation Order, Contract Progress, Contracting Settings); bilingual seed; product docs.

- [ ] **Step 1: Write `insite/insite/workspace/insite/insite.json`**

```json
{
  "doctype": "Workspace", "name": "Insite", "label": "Insite", "title": "Insite",
  "module": "Insite", "public": 1, "icon": "project", "is_hidden": 0,
  "content": "[{\"type\":\"header\",\"data\":{\"text\":\"Setup\",\"level\":4}},{\"type\":\"shortcut\",\"data\":{\"shortcut_name\":\"Work Item Type\"}},{\"type\":\"shortcut\",\"data\":{\"shortcut_name\":\"Contracting Settings\"}},{\"type\":\"header\",\"data\":{\"text\":\"Work\",\"level\":4}},{\"type\":\"shortcut\",\"data\":{\"shortcut_name\":\"Scope Item\"}},{\"type\":\"shortcut\",\"data\":{\"shortcut_name\":\"Variation Order\"}},{\"type\":\"header\",\"data\":{\"text\":\"Reports\",\"level\":4}},{\"type\":\"shortcut\",\"data\":{\"shortcut_name\":\"Contract Progress\"}}]",
  "shortcuts": [
    {"type": "DocType", "link_to": "Work Item Type", "label": "Work Item Type"},
    {"type": "DocType", "link_to": "Contracting Settings", "label": "Contracting Settings"},
    {"type": "DocType", "link_to": "Scope Item", "label": "Scope Item"},
    {"type": "DocType", "link_to": "Variation Order", "label": "Variation Order"},
    {"type": "Report", "link_to": "Contract Progress", "label": "Contract Progress"}
  ]
}
```

- [ ] **Step 2: Write `insite/locale/ar.po`** — header + entries for the key labels (verbatim from spec §8):

```po
msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\nLanguage: ar\n"

msgid "Work Item Type"
msgstr "نوع بند العمل"

msgid "Measurement Rule"
msgstr "قاعدة القياس"

msgid "Scope Item"
msgstr "بند الأعمال"

msgid "Variation Order"
msgstr "أمر تغيير"

msgid "Contract Progress"
msgstr "تقدم العقد"

msgid "Count"
msgstr "العدد"

msgid "Wastage"
msgstr "الهدر"

msgid "Planned Amount"
msgstr "المبلغ المخطط"

msgid "Revised Amount"
msgstr "المبلغ المعدّل"

msgid "How is this measured?"
msgstr "كيف يُقاس هذا؟"
```

- [ ] **Step 3: Write `docs/CONCEPTS.md` and `docs/SETUP.md`** — from spec §2, §4, §5 (Work Item Type / Scope Item / Variation Order / Measurement; and a step-by-step "onboard a Work Item Type → create a Project + Scope Items → quote → order → deliver → invoice → read Contract Progress"). Update `README.md` with product overview + install (`bench get-app`, `bench --site <site> install-app insite`).

- [ ] **Step 4: Validate (JSON parse) & commit**

```bash
python -c "import json; json.load(open('insite/insite/workspace/insite/insite.json', encoding='utf-8')); print('ok')"
git add insite/insite/workspace insite/locale/ar.po docs/SETUP.md docs/CONCEPTS.md README.md
git commit -m "docs: workspace, Arabic seed, SETUP/CONCEPTS, README"
```

---

### Task 18: Full offline validation gate

**Files:** none (validation only).

- [ ] **Step 1: Compile every Python file**

Run: `python -m py_compile $(git ls-files '*.py')`
Expected: no output.

- [ ] **Step 2: Parse every JSON file**

Run: `python -c "import json,glob; [json.load(open(f,encoding='utf-8')) for f in glob.glob('insite/**/*.json', recursive=True)]; print('json ok')"`
Expected: `json ok`.

- [ ] **Step 3: Run the full pure test suite + parity**

Run: `python -m pytest insite/tests -v`
Expected: all pass (measures, formula, resolve, parity, doctype-json).

- [ ] **Step 4: Commit any fixes, then tag readiness**

```bash
git add -A && git commit -m "chore: offline validation gate green" || echo "nothing to commit"
```

---

### Task 19: Push + on-site verification (after user redeploys)

**Files:** none (integration on the test site via the "Contra test mcp" connector).

**Precondition:** the user redeploys on contra.k.frappe.cloud — uninstall old `contracting`, `bench get-app` the `insite` branch, `bench --site contra.k.frappe.cloud install-app insite`, `bench --site … migrate`. (Insite cannot do Frappe Cloud ops; hand these to the user.)

- [ ] **Step 1: Push the branch**

```bash
git push -u origin insite
```

- [ ] **Step 2: Ask the user to redeploy**, then confirm install health via MCP: `get_doctype_info` for `Work Item Type`, `Scope Item`, `Variation Order`; confirm the `scope_item` custom field exists on `Sales Order Item` (DB query); confirm the `Contracting Manager` role and `Contracting Settings` singleton exist.

- [ ] **Step 3: Rebuild the demo via MCP** (data, not app code): a Project; Work Item Types Glass (area) / Aluminium (perimeter) / Metalwork (linear) / Cladding (piece_waste) — including one **Custom formula** measure to exercise the formula path; Scope Items with planned amounts; a Quotation → Sales Order (verify it **refuses to save without Project + Scope**) → partial Delivery Notes → a Sales Invoice; then a **Variation Order** and confirm the Scope Item's Revised Amount updates.

- [ ] **Step 4: Run Contract Progress** and verify the numbers match the constructed scenario (planned/ordered/delivered/invoiced/variance, over-run flag, and revised reflects the variation).

- [ ] **Step 5: Report results** to the user; capture the outcome in memory.

---

## Self-Review

**Spec coverage:**
- §4.1 Work Item Type → Task 8. §4.2 Scope Item → Task 9. §4.3 Variation Order → Task 10. §4.4 Contracting Settings → Task 11. §4.5 roles → Task 16.
- §5 Measurement (presets + formula, Test) → Tasks 2,3,8,14. §6 engine → Tasks 4,12,13. §7 enforcement → Task 13.
- §8 naming/AR → Tasks 8,9,10,17. §9 UX → Task 14,17. §10 Contract Progress → Task 15. §11 non-functional (install/custom fields/dimension/tests/docs) → Tasks 6,7,16,17,18. §12 rollout → Task 19. §14 oracle → Tasks 2–5.
- Gap check: price visibility is a spec item (Contracting Settings) — implemented as a wired stub in Task 11 (full permlevel logic explicitly deferred; noted in code). Acceptable for v1 delivery spine.

**Placeholder scan:** no "TBD/TODO"; the one deliberate deferral (price-visibility permlevel logic) is a documented, safe no-op stub, not a plan gap.

**Type consistency:** `compute(measure, *, height,width,length,count,wastage,formula)` used identically in Tasks 2,3,5,12,14. `resolve_rule(item, rules)` / `rule_score(rule,item)` consistent in Tasks 4,12. Rule dict keys consistent between Task 12 (`load_rules`) and Task 4 (`resolve`). `recompute_revised()` defined in Task 9, called in Task 10. `scope_item` fieldname consistent in Tasks 7,13,15. Custom fieldnames consistent across Tasks 6,12,15.
