# Insite concepts

Insite adds three ideas to ERPNext. Everything else — quotations, orders,
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

A Scope Item belongs to a **Project**, and holds a **Planned Amount**. The
Planned Amount is the agreed baseline value of the scope.

The Contracting Manager types the Planned Amount and can edit it later. When the
client signs a change, set the Planned Amount to the new contract value. Frappe
keeps the change history on the document.

A Scope Item is also an **Accounting Dimension**. Every sales and purchase line
can carry a Scope, so the cost and the revenue stay attached to the work.

## A change of scope

Insite has no change document. A mid-project change of scope is another Sales
Order against the same Scope Item. Many contractors already work this way.

1. The client asks for extra work, or asks you to take work out.
2. Raise a new Sales Order for the change. Use the same Project and the same
   Scope as the original order.
3. For work the client takes out, use the standard ERPNext route. Raise a credit
   note or a return, or raise the follow-on order for the reduced amount.
4. Read the change in **Contract Progress**. Work ordered beyond the plan shows
   as a positive **Variance to Plan**.
5. When the client signs the change, set the **Planned Amount** of the Scope
   Item to the new contract value. The baseline then matches the contract.

Step 5 is optional. Leave the Planned Amount alone to keep the original baseline
in view.

## How the pieces work together

1. You set up the Work Item Types once.
2. You create a Project and its Scope Items, with the planned amounts.
3. Your team quotes, orders, delivers and invoices as usual. Insite calculates
   the quantity of a measured line, and keeps the line tied to its Scope.
4. When the scope changes, you raise another Sales Order against the same Scope
   Item.
5. **Contract Progress** shows, for each scope: planned, ordered, the variance
   to plan, delivered, invoiced, and what is left to invoice.
