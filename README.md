# Insite

Insite is an app for contractors, built on Frappe and ERPNext v16. It turns the
measurements you take on site into billable quantities. It ties the work to a
project and to a scope, and it reports the planned value against the value you
ordered, delivered and invoiced.

## What it adds

- **Work Item Type** — a kind of work, for example `Glass`. It holds a
  description and a switch, nothing more — accounts stay in ERPNext's Item
  Defaults. Its Measurement Rules are listed on the form under **Measurement**.
- **Measurement Rule** — how a kind of work is measured. Say what the rule
  **Applies To**, pick a **Start from**, and read **Worked out as**. That line
  states the calculation in words, for example Height × Width × Count. Ready-made
  starting points: Area, Perimeter, Linear, Count, Piece × Wastage and Volume.
  **Manual** keeps the quantity you typed. **Custom** is for a formula of your
  own.
- **Inputs from three places** — a rule reads a number from the **Line**,
  measured on the document. Or from the **Item**, a number held on the material,
  such as the sheet it is cut from. Or from a **Constant**, a fixed number the
  rule carries, such as a cutting allowance. Nobody retypes a sheet size on every
  line.
- **More numbers from the same measurements** — under **What else these
  measurements give you**, a rule writes further numbers onto the line. For a
  door: the board it consumes, the edging round it, the fittings that go on it.
  The quantity stays what you bill.
- **Measurement Field** — a number Insite does not ship. Give it a label, and say
  whether it belongs on the transaction line or on the Item. Insite adds it
  everywhere it is needed, and adds it again on every migrate.
- **Measurement boxes on the item rows** — Count, Height, Width, Length and
  Wastage. A line shows only the boxes its rule reads. Wastage is a multiplier,
  not a percentage. Type 1.1 to add 10 percent. Leave blank for none.
- **Scope Item** — a scope of work inside a project. It carries a Planned
  Amount, and it acts as an accounting dimension named **Scope**.
- **Project and Scope on sales documents** — Insite asks for a Project on the
  header, and a Scope on each line that a Measurement Rule matched. Insite does
  not check the other lines. You can switch the check off in **Insite Settings**.
- **Rejected work on ERPNext's own Quality Inspection** — Insite adds a **Scope**
  and a **Rejected Qty** to it, and works out what the refused work was worth
  from the rate on the line it came off. A submitted inspection still marked
  Rejected warns you when someone invoices that scope — a setting turns that
  into a refusal to submit — and shows in Contract Progress. Insite writes no
  statuses and posts nothing; settling it stays ERPNext's business.
- **Contract Progress report** — scope, status, planned, ordered, variance to
  plan, delivered, rejected, invoiced, left to invoice and percent invoiced, for
  each scope.

Insite uses standard ERPNext documents on purpose. The Project, the Quotation,
the Sales Order, the Delivery Note, the Sales Invoice and the purchase documents
stay untouched. Insite adds the measurement boxes on the item rows, the Scope
dimension, and its own configuration. It adds nothing else. Everything reports
against two axes: the **Project** and the **Scope Item**.

A change of scope needs no special document. Raise another Sales Order against
the same Scope Item, the way many contractors already work. Contract Progress
then reads the change as **Variance to Plan**.

## Documentation

- [docs/CONCEPTS.md](docs/CONCEPTS.md) — the ideas Insite adds.
- [docs/SETUP.md](docs/SETUP.md) — install, first job, worked example.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — for changing the app: the test gate, and how to get a bench that runs it.

## Install

```bash
bench get-app insite https://github.com/Mina-Geez/contracting --branch insite
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

A document hook calls the calculation on the server before each save of a
Quotation, a Sales Order, a Delivery Note or a Sales Invoice. The server writes
the quantity, so a typed quantity cannot replace a calculated one. A line whose
inputs are all empty keeps the quantity the user typed. Purchase documents carry
the Scope for cost. Insite does not calculate their quantities.

Code creates the measurement boxes on the item rows, the Scope accounting
dimension, the Contracting Manager role and the Insite Settings record. The same
code adds every Measurement Field the site has defined. It runs after install and
after every migrate, and it is safe to run again. Insite does not ship exported
customizations of standard doctypes.

Run the tests:

```bash
python -m pytest insite/tests -v
```

Those tests need no site, and they prove the pure calculation code and the app's
structure — not Frappe's behaviour. Anything touching a Frappe or ERPNext API
has to be run on a real bench before it is trusted.
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) says how to get one, including the two
version floors v16 imposes that most distributions do not meet.
