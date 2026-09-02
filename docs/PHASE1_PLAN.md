# PHASE 1 PLAN — Test instance stand-up, install, verify

**For your approval.** Phase 0 (audit tooling) + the full app build are done this
session. Because production was off-limits, "Phase 1" here is: stand up a fresh
test instance, install the app, then use the shipped audit/parity tooling to reach
ground truth and prove parity — all on non-production infrastructure.

Nothing in this plan touches the live glass site.

---

## Step 1 — Fresh v16 test instance
- New bench (or Frappe Cloud site) on **ERPNext v16**, branch `version-16`.
- Confirm `python ≥ 3.10`, ERPNext installed.
- **Acceptance:** `bench version` shows frappe/erpnext v16; a blank site opens.

## Step 2 — Install the app
```bash
bench get-app contracting <git-url> --branch version-16   # or place local copy in apps/
bench --site <test-site> install-app contracting
bench --site <test-site> migrate
bench --site <test-site> run-tests --app contracting
```
- **Acceptance:**
  - 7 `Calculation Method` records seeded;
  - dimension custom fields present on all 9 item child tables;
  - `Contract Clause` Accounting Dimension created and the post-install field-count
    verification reports **0 missing** (check Error Log for the dimension summary);
  - integration tests green.

## Step 3 — (Optional but recommended) clone the glass site → staging, run the audit
> Only if/when you choose to make a **read-only clone** of the glass site. This is
> the *only* sanctioned way to obtain live ground truth. Never on production.
```bash
bench --site <clone> execute contracting.scripts.audit.run   # writes audit_dump.{json,md}
```
- Fill the **UNVERIFIED** tables in `AUDIT.md` from the dump: versions, custom
  fields, property setters (esp. permlevel), client/server script bodies, the
  per-trade formulas + template/item-group names + dimension fieldnames (incl.
  `custom_عدد_الالواح`), the Contract Clause guards, tolerance value, CoA, the 2
  clause reports + print formats, and ETA/cut-optimization presence.
- **Acceptance (Phase 0 threshold):** 100% of hard-coded formulas, template names,
  and tolerance values catalogued in the `AUDIT.md` extraction table.

## Step 4 — Encode the glass trade as configuration
- Create the **Glass** `Trade Profile`.
- Translate each audited formula into a `Calculation Rule` (method + field
  mappings; point `Base Qty Field` at the live `custom_عدد_الالواح` if that is the
  panel-count field).
- Enter tolerance and CoA mappings; seed a few `Contract Clause` records.
- **Acceptance:** glass fully expressed in config; zero trade-specific constants
  needed in code.

## Step 5 — Parity
- Populate `PARITY.md` / `parity_cases.json` with real submitted input→output rows
  from the clone (per method).
```bash
bench --site <test-site> execute contracting.scripts.parity_harness.run --kwargs "{'cases_file':'parity_cases.json'}"
```
- **Acceptance (gate before any refactor/production consideration):** every
  catalogued case's engine output equals the persisted live qty/amount within the
  recorded tolerance; zero unexplained diffs.

## Step 6 — Second-trade validation (the real test of "no code per trade")
- Onboard a second trade (e.g. aluminium) **purely by configuration** — new Trade
  Profile + Rules, no Python/JS.
- **Acceptance:** second trade produces correct quantities with zero code changes.

---

## Out of scope for Phase 1 (separate R&D — native ERPNext gaps)
BOQ, RA (running-account) billing, retention accounting, cutting-list/nesting, and
Egyptian ETA e-invoicing (pluggable connector; note the 14% construction VAT
reclassification, Law 157/2025). See DECISIONS OQ-9/OQ-10.

## Explicit gates (unchanged, non-negotiable)
- No `bench migrate` carrying any `custom/*.json` sync ever runs against
  production.
- Nothing is installed on the live glass site until parity is proven on the clone.
- Every ERPNext point-release is regression-tested on the clone first.
