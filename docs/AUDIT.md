# AUDIT.md — Phase 0 As-Is Audit of the Live Glass Site

> ⛔ **Production was never contacted in this session.** The user explicitly forbade
> any connection to the live production environment, so the read-only audit sweep
> was **cancelled before execution**. This document is therefore the **audit
> methodology + runnable read-only tooling** to execute on the **staging clone**
> (or, if ever needed, through a strictly read-only, permission-checked connector).
>
> **Every captured value in this document is a template and is `UNVERIFIED`** until
> `contracting/scripts/audit.py` is run against a real site and its output pasted in.
> Do not trust the `compass_artifact_*.md` planning doc as current state — it is a
> recommendations document and contains **none** of the live formulas, tolerances,
> script bodies, template names, or chart-of-accounts mappings.

---

## 0. How to run (on the clone)

The entire Batch A0–A5 query catalog below is packaged as one read-only module:

```bash
# Preferred: runs all queries, returns a dict, and writes audit_dump.json + audit_dump.md
bench --site <clone> execute contracting.scripts.audit.run
```

or interactively:

```bash
bench --site <clone> console
>>> from contracting.scripts import audit
>>> data = audit.run()          # also writes dump files into the site path
```

The module performs **only** `frappe.get_all` / `SELECT` reads — no writes, no
`db_set`, no insert/submit/delete. Each section is isolated in try/except so one
failing query never aborts the run (failures are recorded under `errors`).

> The app does not need to be installed to *read* a site, but importing
> `contracting.scripts.audit` requires the app to be on the bench. If you want to
> audit a clone that does **not** yet have the app, paste the query blocks from
> §2 directly into `bench --site <clone> console`.

---

## 1. Safety constraints (carried from the kickoff)

1. Connector / console access is **read-only**. No write path is assumed.
2. **Never** use "Export Customizations" (`custom/*.json`) sync against the live
   site — its `bench migrate` sync *replaces* all property setters and custom
   permissions. Parity must be proven on the clone before any sync, if ever.
3. `db_set` / `db.set_value` bypass validation, hooks, and version tracking — they
   are **banned** in the app and never used by the audit tooling.

---

## 2. Query catalog (Batch A0–A5)

These are the exact queries `audit.py` runs. Shown here for review and for pasting
into a console on a clone without the app installed.

### A0 — Identity & platform versions (Task A #1)
```python
import frappe
{
  "site": frappe.local.site,
  "company": frappe.db.get_single_value("Global Defaults", "default_company"),
  "installed_apps": frappe.get_installed_apps(),
  "installed_application": frappe.db.sql(
      "SELECT app_name, app_version, git_branch FROM `tabInstalled Application`", as_dict=True),
}
```

### A1 — Custom fields, property setters, permlevel access (Task A #2)
```python
frappe.get_all("Custom Field",
  fields=["name","dt","fieldname","label","fieldtype","options","insert_after",
          "permlevel","depends_on","read_only","reqd","hidden","fetch_from","module"],
  order_by="dt, idx", limit_page_length=0)

frappe.get_all("Property Setter",
  fields=["name","doc_type","field_name","property","property_type","value","module"],
  order_by="doc_type, field_name", limit_page_length=0)   # flag every property == 'permlevel'

frappe.get_all("Custom DocPerm",
  fields=["parent","role","permlevel","read","write","create","submit","cancel","amend"],
  filters={"permlevel": [">", 0]}, order_by="parent, permlevel", limit_page_length=0)
```

### A2 — Client & Server script bodies incl. carry-forward (Task A #2, #4, #8)
```python
frappe.get_all("Client Script", fields=["name","dt","view","enabled","script"], limit_page_length=0)

frappe.get_all("Server Script",
  fields=["name","script_type","reference_doctype","doctype_event","api_method",
          "event_frequency","disabled","script"], limit_page_length=0)
# Carry-forward guards = the subset where doctype_event == "Before Insert".
```

### A3 — Trade templates / calc keying (Task A #3)
```python
frappe.get_all("Item", filters={"has_variants":1},
  fields=["name","item_code","item_name","item_group","stock_uom","variant_based_on"], limit_page_length=0)
frappe.get_all("Item Group", fields=["name","parent_item_group","is_group"], limit_page_length=0)
frappe.get_all("Item Attribute",
  fields=["name","numeric_values","from_range","to_range","increment"], limit_page_length=0)
frappe.get_all("Item Variant Attribute",
  fields=["parent","attribute","attribute_value"], limit_page_length=500)
```

### A4 — Clause subsystem, Accounting Dimension, workflows, tolerance (Task A #4, #6, #10)
```python
frappe.get_all("DocType", filters={"custom":1},
  fields=["name","module","istable","is_submittable","autoname","track_changes"], limit_page_length=0)
frappe.get_all("Accounting Dimension",
  fields=["name","document_type","label","fieldname","disabled"], limit_page_length=0)
frappe.get_all("Workflow",
  fields=["name","document_type","is_active","workflow_state_field"], limit_page_length=0)
frappe.get_all("Workflow Document State",
  fields=["parent","state","doc_status","allow_edit"], limit_page_length=0)
frappe.get_all("Workflow Transition",
  fields=["parent","state","action","next_state","allowed"], limit_page_length=0)
frappe.get_all("Custom Field", filters={"fieldname":["like","%toler%"]},
  fields=["dt","fieldname","label","fieldtype","default"], limit_page_length=0)
```
Then, for whichever DocType turns out to be the clause master, `get_doctype_info`
to dump its field list + the status field `options`, and read the live tolerance
value from its Single/Settings doctype (the fieldname surfaces above first).

### A5 — Reports, print formats, ETA / cut-opt detection, CoA (Task A #5, #7, #9, #11, #12)
```python
frappe.get_all("Report", filters={"is_standard":"No"},
  fields=["name","ref_doctype","report_type","module","disabled","query","report_script","javascript"],
  limit_page_length=0)
frappe.get_all("Print Format", filters={"standard":"No"},
  fields=["name","doc_type","print_format_type","module","disabled"], limit_page_length=0)
frappe.get_installed_apps()
frappe.get_all("DocType", filters={"name":["like","%ETA%"]},
  fields=["name","module","custom"], limit_page_length=0)
frappe.get_all("Scheduled Job Type", fields=["name","method","frequency","stopped"], limit_page_length=0)
frappe.get_all("Account", filters={"is_group":0},
  fields=["name","account_number","account_type","root_type","company"], limit_page_length=0)
```

---

## 3. Results (fill from a real run — currently `UNVERIFIED`)

| # | Capture item | Populated by | Status |
|---|---|---|---|
| 1 | Frappe + ERPNext exact versions | A0 `installed_application` | `UNVERIFIED` |
| 2 | Every Custom Field (name, dt, fieldname, permlevel…) | A1 `custom_fields` | `UNVERIFIED` |
| 3 | Every Property Setter (esp. **all permlevel** setters) | A1 `property_setters` (filter `property=='permlevel'`) | `UNVERIFIED` |
| 4 | Enabled/disabled **Client Scripts** — names + full bodies | A2 `client_scripts` | `UNVERIFIED` |
| 5 | Enabled/disabled **Server Scripts** — names + full bodies | A2 `server_scripts` | `UNVERIFIED` |
| 6 | Quantity calc logic per trade template: exact formulas | A2 script bodies × A3 templates | `UNVERIFIED` |
| 7 | Template / item-group names the formulas key on (`variant_of`) | A3 `item_templates` (`variant_based_on`), `item_groups` | `UNVERIFIED` |
| 8 | Dimension fieldnames incl. Arabic `custom_عدد_الالواح` | A1 `custom_fields` (cross-ref A2 bodies) | `UNVERIFIED` |
| 9 | Contract Clause DocType definition + status options | A4 `custom_doctypes` + `get_doctype_info` | `UNVERIFIED` |
| 10 | Identity-lock / completion-gate / clause-creation guards (full bodies) | A2 `server_scripts` (reference == clause) | `UNVERIFIED` |
| 11 | Carry-forward (Before Insert) scripts across the chain | A2 `server_scripts` where `doctype_event=='Before Insert'` | `UNVERIFIED` |
| 12 | Tolerance policy setting(s) + current value | A4 `tolerance_custom_fields` + Single value read | `UNVERIFIED` |
| 13 | Client-specific chart-of-accounts mappings | A5 `leaf_accounts` (cross-ref A2 bodies for hard-coded account names) | `UNVERIFIED` |
| 14 | The 2 custom clause reports + print formats | A5 `nonstandard_reports`, `print_formats` | `UNVERIFIED` |
| 15 | ETA e-invoicing connector | A5 `installed_apps` + `eta_doctype_hits` + `scheduled_jobs` → else **none found** | `UNVERIFIED` |
| 16 | Cut-optimization in use | A5 `installed_apps`/`custom_doctypes` scan → else **none found** | `UNVERIFIED` |

For items 4/5/9/10/11 the full script bodies are emitted verbatim into
`audit_dump.md` under "Server Scripts (full bodies)" / "Client Scripts (full
bodies)". Paste the relevant ones here once captured.

---

## 4. Hard-coded-value → UI-config extraction table

The core Phase-3 deliverable: every trade-specific constant found in the live
scripts/fields, and where it moves to in the `contracting` app's config model.
**All "current value" cells are `UNVERIFIED`** until the audit runs.

| Hard-coded value | Where found (script / field) | Current value | Extract-to UI config target | Notes |
|---|---|---|---|---|
| Area formula `h × w × qty` | calc Server/Client Script body | `UNVERIFIED` | **Calculation Rule** `calculation_method = area`; map `height_field`, `width_field`, `qty_multiplier_field` | Fixed method; no formula text needed |
| Perimeter formula `(h + w) × 2 × qty` | calc script body | `UNVERIFIED` | **Calculation Rule** `calculation_method = perimeter` | Fixed method |
| Linear formula `length × qty` | calc script body | `UNVERIFIED` | **Calculation Rule** `calculation_method = linear`; map `length_field` | Fixed method |
| Piece × waste-factor | calc script body | `UNVERIFIED` | **Calculation Rule** `calculation_method = piece_waste`; `waste_factor_field` or `waste_factor_value` | Waste as field or constant |
| Any bespoke formula variant | calc script body | `UNVERIFIED` | **Calculation Rule** `calculation_method = formula` + `formula` (Code) | Privileged **Implementer** role only; `frappe.safe_eval` |
| Trade template name(s) (e.g. glass templates) | A3 `item_templates` / calc script string literals | `UNVERIFIED` | **Calculation Rule** `apply_on = Item Template` + `item_template` (or `item_group` / `item_attribute` / `item_code`) | Most-specific-wins resolution |
| Item-group name(s) the calc keys on | A3 `item_groups` / calc script literals | `UNVERIFIED` | **Calculation Rule** `apply_on = Item Group` + `item_group` | |
| Arabic panel-count field `custom_عدد_الالواح` | A1 `custom_fields` | `UNVERIFIED` | **Calculation Rule** `qty_multiplier_field = "custom_عدد_الالواح"` | App ships a generic `custom_base_qty`; the rule can point at the existing Arabic field instead |
| Tolerance value (global) | A4 tolerance field / Single value | `UNVERIFIED` | **Contracting Settings** `default_tolerance_percent` (and optional per-**Trade Profile** / per-**Calculation Rule** override) | Replaces the single global setting |
| CoA: revenue account | A2 script literals × A5 `leaf_accounts` | `UNVERIFIED` | **Trade Profile** CoA-mapping fields (income/expense/retention) | Never fixture GL accounts — map per site |
| CoA: WIP / cost account | A2 script literals × A5 `leaf_accounts` | `UNVERIFIED` | **Trade Profile** CoA-mapping fields | |
| CoA: retention receivable account | A2 script literals × A5 `leaf_accounts` | `UNVERIFIED` | **Contracting Settings** / **Trade Profile** `retention_account` | Only if retention module enabled |
| Price-field permlevel(s) | A1 property setters (`property=='permlevel'`) + `permlevel_custom_docperms` | `UNVERIFIED` | **Contracting Settings** `enable_role_based_price_visibility` + privileged-roles table (applied in code) | Confirms role-based price visibility mechanism |
| Clause status option list | A4 clause DocType `get_doctype_info` | `UNVERIFIED` | **Contract Clause** `status` (Select options) / Workflow | |
| Clause identity-lock field set | A2 clause guard script body | `UNVERIFIED` | **Contract Clause** controller `validate` locked-field list | Reimplemented as controller hook, not Server Script |

---

## 5. Cross-checks to perform once populated

- Reconcile every `permlevel` property setter (A1) against the `permlevel_custom_docperms`
  (A1) to reconstruct the exact **role-based price visibility** matrix.
- Grep every Server/Client script body (A2) for **hard-coded account names** and
  **string literals matching template/item-group names** (A3) — these are the
  extraction candidates that the compass doc could not enumerate.
- Confirm **ETA** (item 15) and **cut-optimization** (item 16): if `installed_apps`
  shows no connector, no `%ETA%` doctype exists, and no scheduled job posts invoices
  externally, record **"none found"** explicitly rather than leaving blank.
- Diff the resulting inventory against the `compass_artifact_*.md` claims and mark
  every divergence — the compass doc is expected to have drifted.

---

*Generated Phase 0. No production data was read to produce this file.*
