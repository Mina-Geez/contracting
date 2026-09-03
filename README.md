# Insite

**Insite** (insight + on-site) is a configuration-driven contracting vertical for
Frappe / ERPNext v16. It turns real-world measurements into billable quantities
automatically, forces every line of work to be tagged to a **Project** and a
**Scope**, and shows planned-vs-actual progress and variance as clients change
scope mid-project.

## What it adds

- **Work Item Type** — the config aggregate root that answers *"how is this
  measured?"* via ready-made measures (Area, Perimeter, Linear, Count,
  Piece × Wastage) or a plain-words **Custom formula**.
- **Measurement engine** — a pure, framework-free calc core (measures +
  sandboxed formula evaluator + most-specific-wins rule resolution) wrapped by
  a server-authoritative `before_validate` hook.
- **Scope Item** — Project-anchored, backs the `scope_item` Accounting
  Dimension, with a stored, auto-recomputed Revised Amount.
- **Variation Order** — submittable; recomputes each referenced Scope Item's
  net variations and revised amount on submit/cancel.
- **Project + Scope enforcement** — a Sales Order (and Delivery Note / Sales
  Invoice) cannot be saved without a Project on the header and a Scope on every
  line.
- **Contract Progress report** — planned → ordered → delivered → invoiced →
  variance, per scope.

## Install

```bash
bench get-app https://github.com/Mina-Geez/contracting --branch insite
bench --site <your-site> install-app insite
bench --site <your-site> migrate
```

## Architecture

A Frappe app `insite` (module `Insite`) layered on ERPNext's transactions, GL,
and Accounting Dimensions. Custom fields, the Scope dimension, roles, and the
Settings singleton are all created idempotently from code — no `db_set`, no
fixtures of standard doctypes, no Export-Customizations sync.

## Tests

```bash
python -m pytest insite/tests -v
```

## License

MIT
