# Insite concepts

Insite adds four ideas to ERPNext. Everything else — quotations, orders,
deliveries, invoices, accounting — stays standard ERPNext.

## Work Item Type

A kind of work you do, and **how it is measured**. Example: "Glass",
"Wood — Doors", "Handrails".

A Work Item Type holds:

- **Measurement Rules** — for a given item or item group, how to turn site
  dimensions into a billable quantity.
- **Default accounts** per company.
- **Tolerance %** for this kind of work.

To add a new kind of work, add a Work Item Type. You do not write code.

## Measurement Rule

One line inside a Work Item Type. It answers: *for this item, how is the
quantity calculated?*

Each rule has a scope (an item, an item group, an item template, or an
attribute value) and a measure. Ready-made measures:

| Measure | Quantity |
| --- | --- |
| Area | Height × Width × Count |
| Perimeter | (Height + Width) × 2 × Count |
| Linear | Length × Count |
| Count | Count |
| Piece × Wastage | Count × Wastage |
| Manual | no calculation; the typed quantity is kept |

If none of these fit, choose **Custom formula** and write the calculation in
plain words, for example `height * width * count * 1.1`. The words you can use
are `height`, `width`, `length`, `count` and `wastage`, with `+ - * / %` and
`abs round min max pow sqrt ceil floor` and `pi`. Formulas are checked when you
save and run on the server only.

When two rules match the same item, the more specific one wins: item, then
template, then attribute value, then item group. Priority breaks a tie.

## Scope Item

A scope of work in a project — the unit you plan, track and report against.
Example: "Curtain wall glazing", "ACP cladding".

A Scope Item belongs to a **Project**, and holds:

- **Planned Amount** — the baseline value at award.
- **Revised Amount** — the current value, after approved changes. Insite keeps
  this up to date; you do not type it.

A Scope Item is also an **Accounting Dimension**. Every sales and purchase line
can carry a Scope, so cost and revenue stay attached to the work.

## Variation Order

An approved change to scope, because clients change their minds.

A Variation Order belongs to a Project and lists the scopes it changes, with the
amount added or removed. Submitting it means approved: each affected Scope Item
gets a new Revised Amount, and the history stays on the document. Cancelling it
puts the values back.

## How the pieces work together

1. You set up Work Item Types once.
2. You create a Project and its Scope Items, with planned amounts.
3. Your team quotes, orders, delivers and invoices as usual. Insite calculates
   the quantity of measured lines and keeps each line tied to its Scope.
4. When scope changes, you raise a Variation Order.
5. **Contract Progress** shows, per scope: planned, variations, revised,
   ordered, delivered, invoiced, and the variance between them.
