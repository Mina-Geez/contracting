# Insite concepts

Insite adds three ideas to ERPNext. Everything else — quotations, orders,
deliveries, invoices, accounting — stays standard ERPNext.

## Work Item Type

A kind of work you do. Example: "Glass", "Wood — Doors", "Handrails".

A Work Item Type holds:

- **Description** — what this kind of work covers.
- **Default accounts** per company.
- **Disabled** — stops every rule for this kind of work.
- **Tolerance %** for this kind of work. Tolerance is on the roadmap. Insite
  stores the number, but nothing acts on it yet. Do not rely on it.

The form lists the rules of this type under **Measurement**. You create a rule
from there.

To add a new kind of work, add a Work Item Type. You do not write code.

## Measurement Rule

A record of its own. It answers one question. For this item, how is the quantity
calculated?

A rule belongs to a Work Item Type. **Applies To** says what the rule covers. It
takes an item, an item group, an item template, or an attribute value. Insite
names each rule after the work and what it covers. Nobody types a code.

A rule is a formula over the fields you choose.

### Inputs

The **Inputs** table is the heart of a rule. Each row picks a number field on
the transaction line. Each row also gives that field a short name for the
formula.

The field list holds Insite's own five measurement fields — Count, Height,
Width, Length and Wastage. It also holds every other number field the site has
added to its sales lines. You pick the field from the list. You never type a
fieldname.

Insite suggests the name from the label of the field. The field "Number of
Panels" becomes `number_of_panels`. Edit the name when you want another one.

### Formula

The **Formula** combines the names of the inputs. Two examples:

- `height * width * count`
- `height * width * number_of_panels * 1.1`

A formula takes the names of the inputs and plain numbers. It also takes the
signs `+ - * / %`, the functions `abs`, `round`, `min`, `max`, `pow`, `sqrt`,
`ceil` and `floor`, and `pi`. Insite checks the formula when you save the rule,
and runs it on the server only.

**Try it** sits on a saved rule. Enter sample numbers, and read the quantity.
The same server code runs here and on a real document.

### Start from

**Start from** offers ready-made starting points. Each one fills in the Inputs
and the Formula for you.

| Start from | Formula it fills in |
| --- | --- |
| Area | `height * width * count` |
| Perimeter | `(height + width) * 2 * count` |
| Linear | `length * count` |
| Count | `count` |
| Piece × Wastage | `count * wastage` |
| Volume | `height * width * length * count` |

A starting point is a start, not a fixed choice. Edit the Inputs, the Formula,
or both.

Two more choices sit in the same list. **Manual** tells Insite never to
calculate the line, and to keep the quantity you typed. **Custom** is for a
formula you write from scratch.

**Wastage** is a multiplier, not a percentage. Type 1.1 to add 10 percent.
Leave blank for none. A value of 10 gives ten times the quantity.

### Which rule runs

When two rules match the same item, the more specific one wins: item, then
template, then attribute value, then item group. Priority breaks a tie between
two rules that are equally specific.

A line whose inputs are all empty is left alone. Insite does not overwrite a
typed quantity when nothing was measured.

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

1. You set up the Work Item Types and their Measurement Rules once.
2. You create a Project and its Scope Items, with the planned amounts.
3. Your team quotes, orders, delivers and invoices as usual. Insite calculates
   the quantity of a measured line, and keeps the line tied to its Scope.
4. When the scope changes, you raise another Sales Order against the same Scope
   Item.
5. **Contract Progress** shows, for each scope: planned, ordered, the variance
   to plan, delivered, invoiced, and what is left to invoice.
