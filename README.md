# Insite

Insite is an app for contractors, built on Frappe and ERPNext v16. It turns the
measurements you take on site into billable quantities. It ties the work to a
project and to a scope, and it reports the planned value against the value you
ordered, delivered and invoiced.

## What it adds

- **Work Item Type** — a kind of work, and how you measure it. One Work Item
  Type holds the measurement rules for a group of items, for example `Glass`.
- **Measurement engine** — Insite reads the Height, Width, Length, Count and
  Wastage on a line. It writes the quantity when you save the document. Wastage
  is a multiplier, not a percentage. Type 1.1 to add 10 percent. Leave blank for
  none.
- **Scope Item** — a scope of work inside a project. It carries a Planned
  Amount and a Revised Amount, and it acts as an accounting dimension named
  **Scope**.
- **Variation Order** — an approved change to a scope. Submit it, and Insite
  updates the Revised Amount of every scope it names.
- **Project and Scope on sales documents** — Insite asks for a Project on the
  header, and a Scope on each line that a Measurement Rule matched. Insite does
  not check the other lines. You can switch the whole check off in
  **Contracting Settings**.
- **Contract Progress report** — planned, net variations, revised, ordered,
  delivered, invoiced and variance, for each scope.

## Documentation

- [docs/CONCEPTS.md](docs/CONCEPTS.md) — the four ideas Insite adds.
- [docs/SETUP.md](docs/SETUP.md) — install, first job, worked example.

## Install

```bash
bench get-app https://github.com/Mina-Geez/contracting --branch insite
bench --site <your-site> install-app insite
bench --site <your-site> migrate
```

## License

MIT

## For developers

The app is `insite` and the module is `Insite`. It sits on ERPNext transactions,
the general ledger and accounting dimensions.

The calculation code is plain Python and does not import Frappe. It holds the
measures, the formula reader and the rule match. The rule match picks the most
specific rule: item, then template, then attribute value, then item group.
Priority breaks a tie.

A document hook calls the calculation on the server before each save. The server
writes the quantity, so a typed quantity cannot replace the calculated one.

Code creates the custom fields on the item rows, the Scope accounting dimension,
the Contracting Manager role and the Contracting Settings record. This code runs
after install and after every migrate, and it is safe to run again. Insite does
not ship exported customizations of standard doctypes.

Run the tests:

```bash
python -m pytest insite/tests -v
```
