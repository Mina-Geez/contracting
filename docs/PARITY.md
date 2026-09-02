# PARITY.md — Calc-Engine Regression Suite (verify-on-clone)

> **No production site was contacted to produce this file.** Every expected value below is an
> `UNVERIFIED` template. This document is the Phase‑2 acceptance gate: during the as‑is
> reimplementation on the **staging clone**, each case's engine output must match the value
> **persisted on the live glass site, byte‑for‑byte, BEFORE any refactor** (Phase 3) begins.
>
> Workflow: run `AUDIT.md` first to discover the live fieldnames and the actual formulas →
> extract real submitted rows from the clone with the queries below → paste them into
> `parity_cases.json` (replacing the UNVERIFIED seeds) → run the harness until every case passes.

---

## 1. Engine contract under test

`contracting.calc.methods.compute(method_key, height=0.0, width=0.0, length=0.0, base_qty=1.0, waste_factor=1.0, formula=None) -> float | None`

| method_key    | formula                                   | notes |
|---------------|-------------------------------------------|-------|
| `area`        | `height * width * base_qty`               | base_qty = piece/panel count |
| `perimeter`   | `(height + width) * 2 * base_qty`         | frame lengths |
| `linear`      | `length * base_qty`                       | running length |
| `piece_waste` | `base_qty * waste_factor`                 | waste_factor ≥ 1.0 |
| `bom_driven`  | `base_qty * waste_factor`                 | line qty only; components exploded by BOM elsewhere → **amount UNVERIFIED (BOM valuation)** |
| `manual`      | `None`                                     | engine leaves user‑entered qty untouched |
| `formula`     | `safe_eval(formula, {height,width,length,base_qty,waste_factor}+math)` | Implementer‑only; needs bench/frappe context |

`amount` in every table = `qty * rate` (ERPNext line amount, before item‑level discount/tax),
which is the number to reconcile against the live `Sales Order Item.amount` etc.

---

## 2. Case tables (populate from the clone; seeds are `UNVERIFIED`)

### area  (qty = h × w × base_qty)
| Case ID | Source Doc / row | height | width | length | base_qty | waste | Expected qty | rate | Expected amount | tolerance | status |
|---------|------------------|-------:|------:|-------:|---------:|------:|-------------:|-----:|----------------:|----------:|--------|
| AREA‑01 | `<SO‑####/1>`    | 1.20   | 2.40  | —      | 3        | —     | 8.640        | 450  | 3888.00         | 0.005     | UNVERIFIED |
| AREA‑02 | `<SO‑####/2>`    | 0.90   | 2.10  | —      | 2        | —     | 3.780        | 450  | 1701.00         | 0.005     | UNVERIFIED |
| AREA‑03 | `<SI‑####/1>`    | 1.50   | 1.50  | —      | 4        | —     | 9.000        | 500  | 4500.00         | 0.005     | UNVERIFIED |

### perimeter  (qty = (h + w) × 2 × base_qty)
| Case ID | Source Doc / row | height | width | length | base_qty | waste | Expected qty | rate | Expected amount | tolerance | status |
|---------|------------------|-------:|------:|-------:|---------:|------:|-------------:|-----:|----------------:|----------:|--------|
| PERI‑01 | `<SO‑####/1>`    | 1.20   | 2.40  | —      | 3        | —     | 21.600       | 30   | 648.00          | 0.005     | UNVERIFIED |
| PERI‑02 | `<SO‑####/2>`    | 0.90   | 2.10  | —      | 2        | —     | 12.000       | 30   | 360.00          | 0.005     | UNVERIFIED |

### linear  (qty = length × base_qty)
| Case ID | Source Doc / row | height | width | length | base_qty | waste | Expected qty | rate | Expected amount | tolerance | status |
|---------|------------------|-------:|------:|-------:|---------:|------:|-------------:|-----:|----------------:|----------:|--------|
| LIN‑01  | `<SO‑####/1>`    | —      | —     | 6.00   | 5        | —     | 30.000       | 40   | 1200.00         | 0.005     | UNVERIFIED |
| LIN‑02  | `<SO‑####/2>`    | —      | —     | 3.50   | 10       | —     | 35.000       | 40   | 1400.00         | 0.005     | UNVERIFIED |

### piece_waste  (qty = base_qty × waste_factor)
| Case ID | Source Doc / row | height | width | length | base_qty | waste | Expected qty | rate | Expected amount | tolerance | status |
|---------|------------------|-------:|------:|-------:|---------:|------:|-------------:|-----:|----------------:|----------:|--------|
| PW‑01   | `<SO‑####/1>`    | —      | —     | —      | 100      | 1.10  | 110.000      | 12   | 1320.00         | 0.005     | UNVERIFIED |
| PW‑02   | `<SO‑####/2>`    | —      | —     | —      | 50       | 1.05  | 52.500       | 12   | 630.00          | 0.005     | UNVERIFIED |

### bom_driven  (qty = base_qty × waste_factor; amount from BOM valuation)
| Case ID | Source Doc / row | height | width | length | base_qty | waste | Expected qty | rate | Expected amount | tolerance | status |
|---------|------------------|-------:|------:|-------:|---------:|------:|-------------:|-----:|----------------:|----------:|--------|
| BOM‑01  | `<WO/SO‑####/1>` | —      | —     | —      | 20       | 1.00  | 20.000       | —    | UNVERIFIED      | 0.005     | UNVERIFIED |

### manual  (qty unchanged — engine returns None)
| Case ID | Source Doc / row | height | width | length | base_qty | waste | Expected qty | rate | Expected amount | tolerance | status |
|---------|------------------|-------:|------:|-------:|---------:|------:|-------------:|-----:|----------------:|----------:|--------|
| MAN‑01  | `<SO‑####/1>`    | —      | —     | —      | —        | —     | 7.000 (as entered) | 200 | 1400.00     | 0.005     | UNVERIFIED |

### formula  (Implementer escape hatch; record the exact live formula string)
| Case ID | Source Doc / row | formula | height | width | length | base_qty | waste | Expected qty | rate | Expected amount | tolerance | status |
|---------|------------------|---------|-------:|------:|-------:|---------:|------:|-------------:|-----:|----------------:|----------:|--------|
| FML‑01  | `<SO‑####/1>`    | `height*width*base_qty*1.1` | 1.20 | 2.40 | — | 3 | 1.10 | 9.504 | 450 | 4276.80 | 0.005 | UNVERIFIED |
| FML‑02  | `<SO‑####/2>`    | `(height*width + (height+width)*2*0.05)*base_qty` | 1.00 | 2.00 | — | 2 | — | 4.400 | 450 | 1980.00 | 0.005 | UNVERIFIED |

> Replace `<SO‑####/n>`, the inputs, `rate`, and the expected columns with **real submitted rows**
> from the clone. Keep the row only after it has been reconciled to the live persisted value.

---

## 3. Extraction queries (run on the CLONE, read-only, docstatus = 1)

The app's fields are `custom_height`, `custom_width`, `custom_length`, `custom_base_qty`,
`custom_waste_factor`. **On the live glass site the fieldnames differ** (e.g. the Arabic panel
count `custom_عدد_الالواح`, and site‑specific height/width fields) — discover the real names via
`AUDIT.md` (Custom Field inventory) first, then substitute them into the `SELECT`s below.

### 3a. Post‑migration (fields already renamed to the app's names on the clone)
```sql
SELECT parent, idx, item_code,
       custom_height, custom_width, custom_length,
       custom_base_qty, custom_waste_factor,
       qty, rate, amount,
       custom_calc_method, custom_calc_rule
FROM   `tabSales Order Item`
WHERE  docstatus = 1
ORDER  BY parent, idx;
```
Repeat for `tabQuotation Item`, `tabSales Invoice Item`, `tabDelivery Note Item`.

### 3b. As-is on the live-clone (map the live Arabic/legacy fieldnames — fill in the `<...>`)
```sql
SELECT parent, idx, item_code,
       `<live_height_field>`   AS height,
       `<live_width_field>`    AS width,
       `<live_length_field>`   AS length,
       `custom_عدد_الالواح`     AS base_qty,   -- panel/sheet count (verify exact name via AUDIT.md)
       `<live_waste_field>`    AS waste_factor,
       qty, rate, amount
FROM   `tabSales Order Item`
WHERE  docstatus = 1
ORDER  BY parent, idx;
```

### 3c. Python extractor → parity_cases.json seed (read-only; run in `bench console` on the clone)
```python
import frappe, json
# map live -> engine field roles AFTER confirming names in AUDIT.md
LIVE = {"height":"custom_height","width":"custom_width","length":"custom_length",
        "base_qty":"custom_عدد_الالواح","waste_factor":"custom_waste_factor"}
rows = frappe.db.sql("""
    SELECT name AS row_id, parent, item_code, {h} AS height, {w} AS width, {l} AS length,
           {b} AS base_qty, {wf} AS waste_factor, qty, rate, amount
    FROM `tabSales Order Item` WHERE docstatus=1
""".format(h=f"`{LIVE['height']}`", w=f"`{LIVE['width']}`", l=f"`{LIVE['length']}`",
           b=f"`{LIVE['base_qty']}`", wf=f"`{LIVE['waste_factor']}`"), as_dict=True)

cases = []
for r in rows:
    cases.append({
        "case_id": f"{r.parent}/{r.row_id}",
        "source_doc": r.parent,
        "method_key": "area",                 # set per Calculation Rule that governs this item
        "height": float(r.height or 0), "width": float(r.width or 0),
        "length": float(r.length or 0), "base_qty": float(r.base_qty or 0),
        "waste_factor": float(r.waste_factor or 1),
        "expected_qty": float(r.qty or 0),
        "rate": float(r.rate or 0), "expected_amount": float(r.amount or 0),
        "tol": 0.005,
    })
open("parity_cases.json","w",encoding="utf-8").write(json.dumps(cases, ensure_ascii=False, indent=2))
print(f"wrote {len(cases)} cases")
```
`method_key` must be assigned per the Calculation Rule that governs each item (join to
Item Group / template) — do not assume all rows are `area`.

---

## 4. How to run the harness

```bash
# On the clone (frappe available); pure calc, no DB writes:
bench --site <clone> execute contracting.scripts.parity_harness.run \
      --kwargs "{'cases_file':'parity_cases.json'}"

# Self-demo with the built-in UNVERIFIED seeds (no file needed):
bench --site <clone> execute contracting.scripts.parity_harness.run
```

Case JSON format (list of objects; mirrors the tables):
```json
[
  {"case_id":"AREA-01","method_key":"area","height":1.2,"width":2.4,"base_qty":3,
   "expected_qty":8.64,"rate":450,"expected_amount":3888.00,"tol":0.005},
  {"case_id":"MAN-01","method_key":"manual","expected_qty":7,"rate":200,"expected_amount":1400.00},
  {"case_id":"FML-01","method_key":"formula","formula":"height*width*base_qty*1.1",
   "height":1.2,"width":2.4,"base_qty":3,"expected_qty":9.504,"rate":450,"expected_amount":4276.80}
]
```
Fields: `method_key` (required); `height/width/length/base_qty/waste_factor` (as needed);
`formula` (formula method); `expected_qty` (required unless `manual`); optional `rate` +
`expected_amount`; optional per‑case `tol` (defaults to the run‑level `tol`, 1e‑6).

---

## 5. Pass criteria (gate for Phase 3)

1. Every catalogued case runs without error.
2. For each case, `|compute(...) − expected_qty| ≤ tol`.
3. Where `rate`/`expected_amount` are recorded, `|qty*rate − expected_amount| ≤ tol`.
4. `manual` cases confirm the engine returns `None` (qty is left as user‑entered).
5. **Zero unexplained diffs.** Any diff must be traced to a known live‑site quirk and either
   reproduced in the engine or explicitly waived in writing before the refactor proceeds.

Only when the whole suite is green against real, reconciled clone data does Phase 3
(refactor hard‑coded values into Trade Profile / Calculation Rule config) begin — and the
suite is re‑run after the refactor to prove the config‑driven engine still matches.
