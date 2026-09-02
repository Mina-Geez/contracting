# DECISIONS — Contracting Vertical App

Design decisions and open questions logged during Phase 0 + scaffold/build.
Session date: **2026-09-02**.

> **Context that shaped everything below:** the user directed that **no production
> environment be touched** this session. The planned read-only live audit was
> therefore **cancelled**, and the app was built **complete and installable** for
> the user to test on a **fresh instance**. Consequence: there is **no live ground
> truth**. The only local input was `compass_artifact_*.md` (a research /
> recommendations document, *not* the as-is glass spec). Every value that would
> normally come from the live site is marked **UNVERIFIED** and must be confirmed
> on a clone using `AUDIT.md` + `PARITY.md`.

---

## Decisions

### D-01 — Package as a code-defined extension app
Own DocTypes + `hooks.py` `doc_events` + bundled JS + **code-defined** custom
fields (`create_custom_fields` in `after_install`/patches).
- **Rejected:** shipping Custom Field / Property Setter as **fixtures** of standard
  doctypes, and the **Export-Customizations (`custom/*.json`) sync** — the latter
  replaces all property setters and custom permissions on every `bench migrate`
  (destructive on a site with hand-made customizations).
- **Why:** upgrade-safe, non-destructive, version-controlled — the pattern ERPNext
  itself uses.

### D-02 — Contract Clause = app DocType **and** Accounting Dimension (both)
A `Contract Clause` master DocType (app-owned) is **registered as an ERPNext
Accounting Dimension**.
- **Why:** the dimension auto-injects a tagging field across the sales/procurement
  chain (Quotation → SO → Delivery/PO → SI/PI → GL) — the most valuable, chain-wide
  mechanism — while the master DocType gives us a real record to hold scope,
  planned values, status, and the identity-lock/completion guards. Extending
  ERPNext's native `Contract` was considered but rejected as the primary vehicle:
  it does not give per-line, chain-wide accounting tagging.
- **Guarded:** dimension field injection is forced **synchronously** and the
  injected **field count is verified and repaired** post-creation (ERPNext #25485
  partial-creation bug).

### D-03 — Calc engine = fixed method enum + privileged formula escape hatch
`Calculation Method` is a seeded registry (area/perimeter/linear/piece_waste/
bom_driven/manual/formula); the computation is code-dispatched in
`contracting/calc/methods.py`.
- The `formula` method uses `frappe.safe_eval` with a **locals dict restricted to
  the declared dimensions + whitelisted math**. Authoring a formula rule is
  restricted (controller check) to `Contracting Implementer` / `System Manager`.
- **Why:** covers the vast majority of trades via the enum without exposing an
  arbitrary-code sandbox to end users.

### D-04 — Rule resolution: most-specific-wins
`Item Code (400) > Item Template (300) > Item Attribute Value (200) > Item Group
(100)`, `priority` (then `modified`) breaks ties within a tier — mirroring ERPNext
Pricing Rule. Item Group matching is **exact** in v1 (ancestor-group matching is a
noted enhancement, see OQ-6).

### D-05 — Idempotent recomputation via dedicated input fields
Dimensions live in dedicated custom fields (`custom_height/width/length/
base_qty/waste_factor`); the engine **derives** `qty` from them and never reads
`qty` as an input for the fixed methods. Re-running `validate` yields the same
result → safe on repeated saves and on carried-forward rows. `base_qty` defaults
to `1.0` when unset (a single unit); `waste_factor` defaults to `1.0`.

### D-06 — Fixtures vs code for master data
Method registry is seeded **in code** (create-if-missing). `Trade Profile`,
`Calculation Rule`, `Contract Clause` are **site-specific config and are NOT
shipped** (they would drag in site-local accounts/warehouses). `fixtures = []`.

### D-07 — License: GPL-3.0-or-later (default)
The app links ERPNext (GPLv3); a distributed derivative is subject to GPL
copyleft. GPLv3 is the conservative, compatible default.
- **Open:** if a proprietary/commercial distribution model is wanted, **obtain
  legal review** before changing this — the GPLv3 linkage is the binding
  constraint. MIT would maximize reuse but does not remove the ERPNext-linkage
  obligation on distribution.

### D-08 — Role-based price visibility: opt-in, reversible
Implemented via **Property Setters** (permlevel 1 on selling price fields) +
**Custom DocPerm** at permlevel 1 for configured roles, driven by
`Contracting Settings`. **OFF by default**; nothing is applied at install.
Refuses to enable with zero roles (would hide prices from everyone). Fully
reverts on disable.

### D-09 — Hook is `before_validate` (not `validate`)
Computing qty in `before_validate` ensures ERPNext's own `validate` →
`calculate_taxes_and_totals` runs **after** our qty is set, so amounts/taxes are
correct. Client JS mirrors the same server engine via a whitelisted API and
`frappe.model.set_value` (never `row.qty = x`).

### D-10 — No `db_set`; documented APIs only
`db_set` / `db.set_value` bypass validation, hooks, and version tracking — banned.
Setup uses `create_custom_fields`, `make_property_setter`,
`frappe.permissions.add_permission`, and normal `doc.insert()/save()`.

---

## Open questions / UNVERIFIED (resolve on the clone)

| # | Question | How to resolve |
|---|---|---|
| OQ-1 | Exact live formulas, template/item-group names, dimension fieldnames (incl. `custom_عدد_الالواح`) | Run `AUDIT.md` batches A1–A3 on the clone; map into Calculation Rules |
| OQ-2 | Current tolerance policy value & semantics | AUDIT batch A4; set on Trade Profile / Contracting Settings |
| OQ-3 | Client-specific chart-of-accounts mappings | AUDIT batch A5; enter in Trade Profile Accounts |
| OQ-4 | Exact identity-lock field set & completion-gate semantics (live guard bodies) | AUDIT batch A2 (script bodies); reconcile `contract_clause.py` `LOCKED_FIELDS` + gate logic |
| OQ-5 | Whether the glass site uses cut-optimization or an ETA e-invoicing connector | AUDIT batch A5 (installed apps / doctypes); state "none" if absent |
| OQ-6 | Item-Group **ancestor** matching (v1 is exact-match only) | Decide after seeing live item-group tree depth |
| OQ-7 | `required_apps = ["frappe","erpnext"]` behaviour on the exact bench version | Verify on the test bench during install |
| OQ-8 | Parity: real input→output cases per method | Populate `PARITY.md` tables from submitted docs on the clone; run `parity_harness` |
| OQ-9 | BOQ / RA (running-account) billing / retention / cutting-list-nesting | Out of MVP scope — separate R&D phase (native gaps in ERPNext) |
| OQ-10 | Egyptian VAT: construction reclassified to **14%** (Law 157/2025) | Configure tax templates on the test instance; not built into the engine |
