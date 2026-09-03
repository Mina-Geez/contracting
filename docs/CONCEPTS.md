# Insite concepts

Insite adds four records to ERPNext: the Work Item Type, the Measurement Rule,
the Measurement Field and the Scope Item. Everything else — quotations, orders,
deliveries, invoices, accounting — stays standard ERPNext.

## Work Item Type

A kind of work you do. Example: "Glass", "Wood — Doors", "Handrails".

A Work Item Type holds:

- **Description** — what this kind of work covers.
- **Default accounts** per company.
- **Disabled** — stops every rule for this kind of work.

The form lists the rules of this type under **Measurement**. You create a rule
from there.

To add a new kind of work, add a Work Item Type. You do not write code.

## Measurement Rule

A record of its own. It answers one question. For this item, how is the quantity
calculated?

A rule belongs to a Work Item Type. **Applies To** says what the rule covers. It
takes an item, an item group, an item template, or an attribute value. Insite
names each rule after the work and what it covers. Nobody types a code.

### Start from, and Worked out as

**Start from** is the only choice most rules need. Each starting point fills in
the whole calculation.

| Start from | What it works out |
| --- | --- |
| Area | Height × Width × Count |
| Perimeter | (Height + Width) × 2 × Count |
| Linear | Length × Count |
| Count | Count |
| Piece × Wastage | Count × Wastage |
| Volume | Height × Width × Length × Count |

**Worked out as** then states the calculation in the words on the form. A rule
that starts from Area reads `Height × Width × Count`. A rule that carries a
cutting allowance reads `Height × Width × Count × 1.12`. Read that one line and
you know what the rule does.

Two more choices sit in the same list. **Manual** tells Insite never to
calculate the line, and to keep the quantity you typed. **Custom** is for a
formula you write from scratch.

**Wastage** is a multiplier, not a percentage. Type 1.1 to add 10 percent.
Leave blank for none. A value of 10 gives ten times the quantity.

### Adjust the measurement

**Adjust the measurement** is a folded-away section. Open it only when the
ready-made answer is not what you measure. It holds the two things behind the
**Worked out as** line: the Inputs and the Formula.

#### Inputs

Each row of **Inputs** is one number the formula reads. **Comes from** says
where that number is.

| Comes from | Where the number is | Example |
| --- | --- | --- |
| Line | measured on the document | the height of this unit |
| Item | held on the material | the sheet the part is cut from |
| Constant | carried by the rule | a cutting allowance of 1.12 |

For **Line** and **Item**, you pick the field from a list. You never type a
field name. For **Constant**, you type the number itself.

**Item** and **Constant** are how a site stops repeating itself. A sheet size
belongs on the material, not retyped on every line. A waste factor belongs on
the rule, not buried in the arithmetic.

Each row also gives the number a short name for the formula. Insite suggests the
name from the label of the field. The field "Number of Panels" becomes
`number_of_panels`. Edit the name when you want another one.

#### Formula

The **Formula** combines the names of the inputs. Two examples:

- `height * width * count`
- `height * width * number_of_panels * 1.1`

A formula takes the names of the inputs and plain numbers. It also takes the
signs `+ - * / %`, the functions `abs`, `round`, `min`, `max`, `pow`, `sqrt`,
`ceil` and `floor`, and `pi`. Insite checks the formula when you save the rule,
and runs it on the server only.

**Try it** works out one quantity from sample numbers. It asks you for the
numbers the line supplies. It uses the constants the rule carries, and it counts
a number from the Item as 1. The same server code runs here and on a real
document.

### What else these measurements give you

A rule can produce more than one number. This second folded-away section writes
further numbers onto the line from the same measurements. For a door: the board
it consumes, the edging round it, the fittings that go on it.

Each row names a field on the line, and a formula over the same input names. The
quantity stays what you bill. Insite writes the other numbers beside it.

Two limits hold. A rule may not write to a field it reads. A rule may not write
to the same field twice. Insite refuses both when you save the rule.

### Which rule runs

When two rules match the same item, the more specific one wins: item, then
template, then attribute value, then item group. Priority breaks a tie between
two rules that are equally specific.

A line whose inputs are all empty is left alone. Insite does not overwrite a
typed quantity when nothing was measured.

When no rule matches a line any more, Insite clears what it wrote and says so.
The quantity stays as it is, because it belongs to the person who typed it.

## Measurement Field

A number your site measures that Insite does not ship.

Give the field a **Label**, for example "Number of Panels". **Where it belongs**
says which kind of number it is.

- **Transaction line** — measured each time, like a panel count.
- **Item** — true of the material, like the sheet it is cut from.

Insite adds the field everywhere it is needed, and adds it again on every
migrate. A rule then reads it like any other number.

**Used by rules** lists the rules that read the field. A field a rule uses cannot
be deleted. To take the box off the documents and keep everything already
entered in it, tick **Hide on documents**.

## On a transaction line

A line shows only the measurement boxes its rule reads. A door type that never
uses Length does not offer a Length box.

The quantity and the amount follow the measurements as you type them. The server
works the quantity out again when you save, so the saved quantity is always the
server's.

The **Scope** list offers only the scopes on the project of this document. A new
line takes the Scope from the line above it.

## Scope Item

A scope of work in a project — the unit you plan, track and report against.
Example: "Curtain wall glazing", "ACP cladding".

A Scope Item belongs to a **Project**, and holds a **Planned Amount**. The
Planned Amount is the agreed baseline value of the scope. **Planned Qty** and
**UOM** are for your own reference. Insite does not calculate with them.

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

1. You set up the Work Item Types and their Measurement Rules once. You add a
   Measurement Field for any number Insite does not ship.
2. You create a Project and its Scope Items, with the planned amounts.
3. Your team quotes, orders, delivers and invoices as usual. Insite calculates
   the quantity of a measured line, writes any other numbers the rule produces,
   and keeps the line tied to its Scope.
4. When the scope changes, you raise another Sales Order against the same Scope
   Item.
5. **Contract Progress** shows, for each scope: planned, ordered, the variance
   to plan, delivered, invoiced, and what is left to invoice.
