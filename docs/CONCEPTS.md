# Insite concepts

Insite adds four ideas to ERPNext. Everything else — quotations, orders,
deliveries, invoices, accounting — stays standard ERPNext.

## Work Item Type

A kind of work you do, and **how it is measured**. Example: "Glass",
"Wood — Doors", "Handrails".

A Work Item Type holds:

- **Measurement Rules** — for a given item or item group, how to turn the site
  dimensions into a billable quantity.
- **Default accounts** per company.
- **Tolerance %** for this kind of work. Tolerance is on the roadmap. Insite
  stores the number, but nothing acts on it yet. Do not rely on it.

To add a new kind of work, add a Work Item Type. You do not write code.

## Measurement Rule

One line inside a Work Item Type. It answers one question. For this item, how is
the quantity calculated?

Each rule names what it applies to, and how to measure it. **Applies To** takes
an item, an item group, an item template, or an attribute value. **Measured By**
takes one of these ready-made measures.

| Measured By | Quantity |
| --- | --- |
| Area (Height × Width × Count) | Height × Width × Count |
| Perimeter ((Height + Width) × 2 × Count) | (Height + Width) × 2 × Count |
| Linear (Length × Count) | Length × Count |
| Count | Count |
| Piece × Wastage (Count × Wastage) | Count × Wastage |
| Manual (keep the typed quantity) | Insite keeps the quantity you typed |

**Wastage** is a multiplier, not a percentage. Type 1.1 to add 10 percent.
Leave blank for none. A value of 10 gives ten times the quantity.

If none of these fit, choose **Custom formula** and write the calculation in
plain words, for example `height * width * count * 1.1`. The words you can use
are `height`, `width`, `length`, `count` and `wastage`, with `+ - * / %` and
`abs round min max pow sqrt ceil floor` and `pi`. Insite checks a formula when
you save it, and runs it on the server only.

When two rules match the same item, the more specific one wins: item, then
template, then attribute value, then item group. Priority breaks a tie.

## Scope Item

A scope of work in a project — the unit you plan, track and report against.
Example: "Curtain wall glazing", "ACP cladding".

A Scope Item belongs to a **Project**, and holds:

- **Planned Amount** — the baseline value at award.
- **Revised Amount** — the current value, after the approved changes. Insite
  keeps this up to date. You do not type it.

A Scope Item is also an **Accounting Dimension**. Every sales and purchase line
can carry a Scope, so the cost and the revenue stay attached to the work.

## Variation Order

An approved change to the scope of a project.

A Variation Order belongs to a Project. It lists the scopes it changes, and the
amount of each change. To submit it is to approve it. Each named Scope Item then
gets a new Revised Amount, and the history stays on the document. Canceling the
Variation Order puts the values back.

### Add, Omit and Modify

Each line carries a **Type**. The Type sets the direction of the change, so you
always type a positive **Amount Change**.

| Type | Effect on the scope |
| --- | --- |
| Add | Insite adds the amount. Use it for new work. |
| Omit | Insite subtracts the amount. Use it for work you take out. |
| Modify | Insite adds the amount. Use it to change work already in the scope. |

To take work out of a scope, type the amount as a positive number and pick
`Omit`. Do not type a negative amount.

## How the pieces work together

1. You set up the Work Item Types once.
2. You create a Project and its Scope Items, with the planned amounts.
3. Your team quotes, orders, delivers and invoices as usual. Insite calculates
   the quantity of a measured line, and keeps the line tied to its Scope.
4. When the scope changes, you raise a Variation Order.
5. **Contract Progress** shows, for each scope: planned, variations, revised,
   ordered, delivered, invoiced, and the variance between them.
