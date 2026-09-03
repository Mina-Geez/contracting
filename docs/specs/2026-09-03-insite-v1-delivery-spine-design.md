# Insite — v1 Delivery Spine — Design Spec

- **Date:** 2026-09-03
- **Status:** Draft for review (brainstorming output; not yet approved for implementation)
- **Product/brand:** **Insite** (insight + on-site)
- **Technical Frappe app name:** `insite`
- **Repo/branch:** fresh branch `insite` in the existing `Mina-Geez/contracting` repo
- **Platform:** Frappe / ERPNext v16 (branch `version-16`)
- **Predecessor:** the `contracting` app (built + validated on contra.k.frappe.cloud). This is a **ground-up rewrite as a product**; the old app's calc logic, unit tests, and parity harness are carried forward as the **correctness oracle**, not copied wholesale.

---

## 1. Purpose & guiding principles

Insite is a **generic, configuration-driven contracting app** for Frappe/ERPNext that helps a contractor manage the messiness of the business: it turns real-world **measurements into billable quantities automatically**, forces every line of work to be tagged to a **project and a scope**, and shows **planned-vs-actual progress and variance** as clients change scope mid-project.

**Guiding principles:**
- **Contractor-first, not developer-first.** Implementors never type a fieldname, code, or identifier. Everything is an auto-number + a plain Title, chosen from dropdowns/toggles, or written as a plain-words formula.
- **Ride ERPNext, don't rebuild it.** Quotation/SO/DN/SI, PO/PR/PI, GL, and Accounting Dimensions are ERPNext's. Insite adds only the contracting layer.
- **Don't over-engineer.** Model exactly the spine the business runs on; defer everything else to named later phases.
- **Server-authoritative & reproducible.** Quantities computed in `before_validate`; no `db_set`, no fixtures of standard doctypes, no Export-Customizations sync; everything installs idempotently from code.

## 2. The core workflow (what the app is for)

1. **Setup (once):** the contractor defines each **Work Item Type** by answering *"how is this measured?"* — e.g. Glass = Height × Width × Count; a wood item = its own formula.
2. **Quotation:** the team quotes work as normal; Insite auto-computes each line's quantity from the dimensions they enter.
3. **On acceptance → Sales Order:** the app **will not let a Sales Order be saved without a Project on the header and a Scope on every line.** This is the enforcement that keeps the job trackable.
4. **Delivery & Invoicing:** Delivery Notes and Sales Invoices carry the same scope tags and auto-computed quantities.
5. **Client changes their mind:** a **Variation Order** adjusts the scope's value; the Revised Amount updates automatically with full history.
6. **Progress:** the **Contract Progress** report shows, per scope, planned → ordered → delivered → invoiced → variance.

## 3. Scope

### In scope (v1 — "delivery spine")
Work Item Types (with "how is this measured?" incl. custom formulas) · the measurement engine · Scope Items under a Project · Variation Orders · Project+Scope enforcement on Sales Orders (and downstream) · the sell cycle on ERPNext · the Contract Progress report · light buy-side scope tagging · product-grade polish (bilingual, clean workspace, docs, idempotent install).

### Out of scope (named later phases, each its own spec)
- **Phase 2 — Billable Expenses (reimbursable / pass-through costs):** flag a **Purchase Invoice item** (or expense) as **Billable** and tag customer + project + scope. The billable cost posts to a **"Billable Expenses" control account** (under Expenses); its balance = costs incurred but not yet re-billed to the client ("in custody"). **Invoicing the customer relieves the account.** Includes an *unbilled billable costs* list (by customer/project/scope) and a *"pull billable items into a Sales Invoice"* action that performs the relief. Reuses the v1 Scope dimension. **This is what the user means by "customer custody" — distinct from advance payments.** Open Phase-2 design points: control-account placement / P&L timing (asset-WIP vs expense-group contra); re-bill at cost vs cost-plus-markup. *(Designed-for in v1 — the Scope dimension already flows to purchase docs — but not built yet.)*
- **Phase 3 — Cost Control:** committed-vs-actual cost per scope, margin/P&L, subcontractors (buy-side first-class).
- **Later:** Estimation/BoQ & tender; progress billing/IPC, retention; customer-supplied ("free-issue") materials.

## 4. Domain model (DocTypes)

Internal fieldnames are clean snake_case; **labels** are the human/contractor-facing bilingual text.

### 4.1 Work Item Type (aggregate root; master) — *(was "Trade Profile"/"Discipline")*
The answer to *"what kind of work is this and how is it measured?"*
| field | type | notes |
|---|---|---|
| `work_item_type_name` | Data (unique) | e.g. "Glass", "Wood — Doors" |
| `disabled` | Check | |
| `description` | Small Text | |
| `tolerance_percentage` | Percent | planned-vs-executed tolerance for this type |
| **Default Accounts** | child `Insite Type Account` | per company: income / expense / cost center |
| **Measurement Rules** | child `Measurement Rule` | how items of this type are measured — see §5 |

Visible dimension inputs on transaction lines are **derived automatically** from the measures actually used (a rule that measures by Area surfaces Height/Width/Count), so there is no separate "visible dimensions" configuration to maintain.

### 4.2 Scope Item (backs the Accounting Dimension; lives under a Project) — *(was "Contract Clause")*
| field | type | notes |
|---|---|---|
| name | autoname `SC-.YYYY.-` | **auto-numbered**; implementor types only the Title |
| `scope_title` | Data | the only identifier typed — a plain description |
| `project` | Link Project (**mandatory**) | the anchor (no separate Contract doctype) |
| `customer`,`company`,`currency` | fetched from Project | |
| `status` | Select | Draft/Active/On Hold/Completed/Cancelled |
| `disabled` | Check | hides from dimension pickers |
| `scope_description` | Text Editor | |
| `original_planned_amount` | Currency | baseline ("Planned Amount") |
| `original_planned_qty` | Float | |
| `uom` | Link UOM | |
| `net_variations_amount` | Currency (read-only) | = Σ approved Variation Order deltas |
| `revised_planned_amount` | Currency (read-only) | = original + net variations; **stored, auto-recomputed** on VO submit/cancel |

**Accounting Dimension:** injected on transactions as fieldname `scope_item` (label "Scope"), pointing here. Post-install field-count guard (#25485).

### 4.3 Variation Order (submittable; under a Project) — *(new; the dynamic-scope engine)*
| field | type | notes |
|---|---|---|
| name | autoname `VO-.YYYY.-` | |
| `project` | Link Project | |
| `customer` | fetched | |
| `date`, `reason`, `description` | | |
| status | via docstatus | Draft / Submitted(=Approved) / Cancelled |
| **Variation Lines** | child `Variation Line` | `scope_item`, `change_type` (Add/Omit/Modify), `delta_qty`, `delta_amount`, `note` |

`on_submit`/`on_cancel`: idempotently recompute each referenced Scope Item's `net_variations_amount` + `revised_planned_amount` (= Σ deltas of all submitted lines for that scope) via `frappe.get_doc(scope).save()` — self-healing, no `db_set`.

### 4.4 Contracting Settings (single)
Role-based price visibility (enable + roles) and default tolerance %. Relabelled, bilingual.

### 4.5 Roles (kept minimal)
- **Contracting Manager** — configures Work Item Types (including authoring measurement formulas), manages scopes and variations, runs the sell cycle.
- Read-only: Accounts / Sales / Purchase users on Scope Items and the report.

*(No separate "Administrator" role: measurement formulas run in a safe sandbox, so the Manager can author them directly. No implementor-facing fieldname mapping exists — the app owns its standard dimension fields.)*

## 5. Measurement — "How is this measured?"

This is the heart of the app and the setup screen the contractor actually thinks about. Each **Measurement Rule** (a row on a Work Item Type) says: *for this item / item group, measure it like this.*

- **Applies to:** Item, Item Group, Item Template, or Attribute value (dropdowns) + a priority. Most-specific wins at transaction time (Item Code > Template > Attribute > Group).
- **Measure:** either
  - a **ready-made measure** (built-in named formulas): **Area** = Height × Width × Count · **Perimeter** = (Height + Width) × 2 × Count · **Linear** = Length × Count · **Count** · **Piece × Wastage** = Count × Wastage; or
  - **Custom formula** — a plain-words expression, e.g. `Height × Width × Count × 1.1`, using the words **Height, Width, Length, Count, Wastage** (shown as clickable chips) plus basic math. The inputs the formula references decide which dimension fields appear on the line.
- **Test:** a **Test** button computes a sample so the contractor sees the result before going live.

**Safety & mechanics:** formulas run server-side in a restricted sandbox (only those words + whitelisted math — abs/round/min/max/pow/sqrt/ceil/floor/pi); nothing else is in scope. Plain words map to the app's standard line fields (`custom_height`, `custom_width`, `custom_length`, `custom_base_qty`, `custom_waste_factor`) behind the scenes — the contractor never sees a fieldname. The pure calc functions (Area/Perimeter/… and the formula evaluator) are the carried-forward, test-covered engine.

## 6. Calc engine (carried forward; verified against the oracle)
- **`insite/calc/methods.py`** — pure functions: the ready-made measures + the plain-words formula evaluator. No Frappe import except lazily for `safe_eval`.
- **`insite/calc/engine.py`** — load enabled Work Item Types, flatten their Measurement Rules into resolvable rules, resolve most-specific-wins per item, compute, write `qty` + audit fields.
- **`insite/overrides/transaction.py`** — `before_validate` on Quotation/Sales Order/Delivery Note/Sales Invoice (+ light `scope_item` tagging on purchases). **Plus** the Project+Scope **enforcement** on Sales Order and downstream (see §7).
- **Custom fields (code-defined)** on sales/purchase item child tables: inputs `custom_base_qty` ("Count"), `custom_height`, `custom_width`, `custom_length`, `custom_waste_factor` ("Wastage"); audit `custom_calculated_qty`, `custom_calc_measure`, `custom_calc_source` (e.g. "Glass"), `custom_calc_dimensions` (JSON); plus the `scope_item` dimension.

## 7. Enforcement (the "keeps the job trackable" bit)
- A **Sales Order cannot be saved** unless the header has a **Project** and **every item line has a Scope**. Clear, plain error messages ("Add a Project", "Row 3: choose a Scope").
- Same requirement carried to Delivery Note and Sales Invoice.
- Quotation stays unconstrained (early stage), but pre-fills scope where known so acceptance→SO is smooth.

## 8. Naming / labelling (product vocabulary, bilingual)

| Concept | Label (EN) | AR (approved) |
|---|---|---|
| Config aggregate | **Work Item Type** | نوع بند العمل |
| How it's measured (rule) | **Measurement Rule** | قاعدة القياس |
| Ready-made measures | Area / Perimeter / Linear / Count / Piece × Wastage | مساحة / محيط / طولي / عدد / قطعة × هدر |
| Custom measure | **Custom formula** | معادلة مخصصة |
| Scope/BoQ line | **Scope Item** (dimension label "Scope") | بند الأعمال |
| Scope change | **Variation Order** | أمر تغيير |
| Progress report | **Contract Progress** | تقدم العقد |
| Count input | **Count** | العدد |
| Wastage input | **Wastage** | الهدر |
| Baseline / revised | **Planned Amount** / **Revised Amount** | المبلغ المخطط / المبلغ المعدّل |

All labels bilingual (EN default; AR in `insite/locale/ar.po`); RTL-friendly.

## 9. UX
- **Nothing technical typed by implementors** — auto-numbers + Titles + dropdowns/toggles; formulas use plain words, never fieldnames.
- Measurement setup reads as *"how is this measured?"* with ready-made measures, a custom-formula option, and a live **Test**.
- **Clean Workspace** ("Insite"): **Setup** (Work Item Types, Settings) · **Work** (Scope Items, Variation Orders) · **Reports** (Contract Progress), in that order, with onboarding steps.

## 10. Reporting — Contract Progress
Per Scope Item (filterable by Project / status): Scope · Title · Status · **Planned · Net Variations · Revised · Ordered · Delivered · Invoiced** · Variance (Revised − Invoiced) · % Invoiced · **Over-run flag** (when ordered/delivered/invoiced exceeds revised). Ordered = Σ submitted Sales Order lines by scope; Delivered = Σ Delivery Notes; Invoiced = Σ Sales Invoices. Totals row included.

## 11. Non-functional / product-grade
Generic (no client-specific logic; examples only in help text) · bilingual EN/AR, RTL-aware · idempotent install (`after_install`/`after_migrate` + patches: custom fields, `scope_item` dimension with guard, roles, Settings singleton) · no `db_set` / no fixtures / no Export-Customizations · docs (`README`, `docs/SETUP`, `docs/CONCEPTS`, `CHANGELOG`) · tests: pure calc unit tests (carry + extend), parity harness vs the old engine, Variation→Revised tests, report aggregation test, plus py_compile/JSON/RO checks — all green before push.

## 12. Rollout
App `insite` on a fresh branch `insite` in `Mina-Geez/contracting`, built and validated there; the user redeploys on Frappe Cloud. On the test site: uninstall the old `contracting` app + wipe its demo data, install `insite`, seed, and rebuild the "Nile Tower" demo on the new model (Work Item Types + Project + Scope Items) **plus a Variation Order** to re-prove progress/variance end-to-end.

## 13. Resolved decisions (2026-09-03)
App name `insite`; fresh branch `insite` in existing repo; **Work Item Type** (not Discipline/Trade); **Project-anchored, no custom Contract**; **custom formulas are first-class** (Manager-authored, plain words, sandboxed); AR terms approved; Scope Items auto-numbered; implementors never type fieldnames/codes; **"Customer custody" clarified = billable/reimbursable expenses** (billable flag on PI items/expenses → a Billable Expenses control account relieved when the customer is invoiced) → **Phase 2**; NOT advance payments; roles trimmed to Manager + read-only; Measurement Method registry doctype dropped in favor of inline ready-made measures + custom formula.

## 14. Correctness oracle (must not regress)
The old `contracting` engine's pure results and its 11 unit tests define correct behavior. The new engine must reproduce them exactly (via the parity harness) before v1 is considered functionally complete.
