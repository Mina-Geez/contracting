# Insite

Insite is an app for contractors, built on Frappe and ERPNext v16. It turns the
measurements you take on site into billable quantities. It ties the work to a
project and to a scope, and it reports the planned value against the value you
ordered, delivered and invoiced.

## What it adds

- **Work Item Type** — a kind of work, for example `Glass`. It holds a
  description, the default accounts per company and the options. Its Measurement
  Rules are listed on the form under **Measurement**.
- **Measurement Rule** — a record of its own. Pick the fields the rule reads
  from the line, then write the formula that combines them. Ready-made starting
  points fill in both: Area, Perimeter, Linear, Count, Piece × Wastage and
  Volume. Edit what a starting point gives you. A rule reads any number field on
  the line, including a field your site added itself. Insite writes the quantity
  when you save the document.
- **Measurement fields on the item rows** — Count, Height, Width, Length and
  Wastage. Wastage is a multiplier, not a percentage. Type 1.1 to add 10
  percent. Leave blank for none.
- **Scope Item** — a scope of work inside a project. It carries a Planned
  Amount, and it acts as an accounting dimension named **Scope**.
- **Project and Scope on sales documents** — Insite asks for a Project on the
  header, and a Scope on each line that a Measurement Rule matched. Insite does
  not check the other lines. You can switch the whole check off in
  **Contracting Settings**.
- **Contract Progress report** — scope, status, planned, ordered, variance to
  plan, delivered, invoiced, left to invoice and percent invoiced, for each
  scope.

Insite uses standard ERPNext documents on purpose. The Project, the Quotation,
the Sales Order, the Delivery Note, the Sales Invoice and the purchase documents
stay untouched. Insite adds the measurement fields on the item rows, the Scope
dimension, and its own configuration. It adds nothing else. Everything reports
against two axes: the **Project** and the **Scope Item**.

A change of scope needs no special document. Raise another Sales Order against
the same Scope Item, the way many contractors already work. Contract Progress
then reads the change as **Variance to Plan**.

## Documentation

- [docs/CONCEPTS.md](docs/CONCEPTS.md) — the three ideas Insite adds.
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
starting points, the formula reader and the rule match. The rule match picks the
most specific rule: item, then template, then attribute value, then item group.
Priority breaks a tie.

A document hook calls the calculation on the server before each save. The server
writes the quantity, so a typed quantity cannot replace a calculated one. A line
whose inputs are all empty keeps the quantity the user typed.

Code creates the custom fields on the item rows, the Scope accounting dimension,
the Contracting Manager role and the Contracting Settings record. This code runs
after install and after every migrate, and it is safe to run again. Insite does
not ship exported customizations of standard doctypes.

Run the tests:

```bash
python -m pytest insite/tests -v
```
