# Contracting

A **generic, UI-configurable contracting vertical** for Frappe/ERPNext **v16**.
Onboard any trade — glass, wood/joinery, aluminium, civil — by **configuration,
not per-client code**. It generalizes a single-client glass-contracting ERPNext
deployment into a distributable extension app.

> Branch: `version-16` · License: GPL-3.0-or-later (see `license.txt` / DECISIONS.md D-07)

---

## What it provides

- **Dimension-driven quantity engine** — a fixed enum of calculation methods plus
  a privileged formula escape hatch:
  | method | qty formula |
  |---|---|
  | `area` | height × width × base_qty |
  | `perimeter` | (height + width) × 2 × base_qty |
  | `linear` | length × base_qty |
  | `piece_waste` | base_qty × waste_factor |
  | `bom_driven` | base_qty × waste_factor (components explode via BOM) |
  | `manual` | user-entered qty kept as-is |
  | `formula` | `frappe.safe_eval` over the declared dimensions (Implementer only) |
- **Config, not code** — `Trade Profile`, `Calculation Rule`, `Calculation Method`
  DocTypes. A rule links a scope (Item Code / Template / Attribute value / Item
  Group, most-specific-wins) to a method and to the line fieldnames holding each
  dimension. New trade = new Trade Profile + Rules, zero Python/JS edits.
- **Contract Clause / scope-of-work** — an app-owned `Contract Clause` master
  registered as an ERPNext **Accounting Dimension**, so a clause tag flows
  Quotation → SO → Delivery/PO → SI/PI → GL for per-scope reporting. Includes
  identity-lock and completion-gate controller guards.
- **Server-authoritative calculation** — qty is computed in a `before_validate`
  doc event, so it is correct for normally-entered rows **and** for
  `get_mapped_doc`-carried rows (which never fire client triggers). Client JS is
  UX-only and uses `frappe.model.set_value`.
- **Management report** — *Clause Portfolio*: planned vs delivered vs invoiced per
  scope.
- **Role-based price visibility** — optional, reversible, OFF by default.
- **Bilingual** — seed `ar.po`; regenerate with `bench generate-pot-file`.

## Architecture guarantees (upgrade-safe by design)

- Custom fields on standard doctypes are **code-defined** (`after_install` /
  patches via `create_custom_fields`), **never** shipped as `Custom Field`
  fixtures and **never** via the destructive Export-Customizations (`custom/*.json`)
  sync.
- No `db_set` / `db.set_value`; documented APIs only.
- All setup is **idempotent** and re-run on `after_migrate`.

---

## Requirements

- A Frappe/ERPNext **v16** bench (Python ≥ 3.10, ERPNext installed).

## Install

This folder **is** the app (`contracting`). Put it on your bench and install:

```bash
# from your frappe-bench directory
# option A — app is a git repo you host:
bench get-app contracting <git-url> --branch version-16

# option B — local copy: place this folder at apps/contracting, then:
bench build --app contracting

# install onto a site (use a fresh TEST site — never production):
bench --site <your-test-site> install-app contracting
bench --site <your-test-site> migrate
```

On install/migrate the app idempotently:
1. creates roles `Contracting Manager`, `Contracting Implementer`;
2. seeds the `Calculation Method` registry (7 methods);
3. creates the dimension custom fields on all sales/purchase item tables;
4. creates the `Contract Clause` **Accounting Dimension** and **verifies the
   injected field count**, repairing any gap (guards ERPNext bug #25485);
5. materializes `Contracting Settings` (price visibility OFF).

## Configure (5-minute glass example)

1. **Trade Profile** → New → “Glass”. Set tolerance %, visible dimensions.
2. **Calculation Rule** → New:
   - Apply On = `Item Group` → “Glass” (or Item Template for a variant family)
   - Calculation Method = `area`
   - Height Field = `custom_height`, Width Field = `custom_width`
   - Base Qty Field = `custom_base_qty` *(or your site's `custom_عدد_الالواح`)*
   - Target Field = `qty` (default)
3. On a **Quotation/Sales Order**, add a glass item, expand **Contracting —
   Dimensions**, enter height/width/base qty → `qty` computes to the area, and
   amount follows.
4. **Contract Clause** → New (e.g. `FACADE-01`) → tag it on line items via the
   *Contract Clause* dimension field → run **Clause Portfolio** report.

## Verify against the live site (on a clone — never production)

Two tools ship with the app for the audit/parity workflow (see `../AUDIT.md`,
`../PARITY.md`):

```bash
# read-only inventory dump of an existing site (run on the CLONE)
bench --site <clone> execute contracting.scripts.audit.run
# calc regression against captured input->output cases
bench --site <clone> execute contracting.scripts.parity_harness.run --kwargs "{'cases_file':'parity_cases.json'}"
```

## Tests

```bash
# pure calc unit tests (no site needed)
python -m unittest contracting.tests.test_calc_methods
# full integration tests under bench
bench --site <site> run-tests --app contracting
```

## Safety

- Install and test on a **fresh instance / staging clone only**. Do not install
  on the live glass production site until parity is proven on the clone.
- Role-based price visibility changes permlevels site-wide when enabled — validate
  on the clone before using in production.
