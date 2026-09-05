# Insite concepts

Insite adds three records to ERPNext: the Measurement Rule, the Measurement
Field and the Scope Item. Everything else — quotations, orders,
deliveries, invoices, accounting — stays standard ERPNext.

## Measurement Rule

A record of its own. It answers one question. For this item, how is the quantity
calculated?

**Applies To** says what the rule covers. It
takes an item, an item group, a brand, an item template, or an attribute value. Insite
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

When two rules match the same item, the more specific one wins. The order is
the one ERPNext already teaches on the Item, so there is no second convention to
learn: a default on the item beats one on its brand, which beats one on its item
group.

| Applies To | Covers |
| --- | --- |
| **Item Code** | this one item |
| **Item Template** | every variant of a template |
| **Item Attribute Value** | every item with an attribute, such as 6mm |
| **Brand** | every item of a make |
| **Item Group** | every item in a group, **and in the groups beneath it** |

**Item Group is a tree, and a rule on a parent reaches everything under it** —
the way an Item Default does. A rule on `Products` covers `Products > Glazing`
until someone writes one on `Glazing`, which is nearer and wins. A nearer group
never outranks a brand, however deep the tree goes.

Priority breaks a tie between two rules that are equally specific.

An **Item Group**, a **Brand** and an **Item** each say at the top of their form
which rule measures them, and name the group a rule was inherited from. Where
none does, **Measure This** writes one from there: being on the record is what
says what the rule applies to, so the only question asked is how it is measured.

The rule stays its own record — reusable, prioritised, able to cover a group, a
brand, a template or one item — but you no longer have to know that to find it,
or to write one.

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

**You do not type the Planned Amount.** Nobody knows a scope's value when they
create it, and a number typed in two places is how two numbers come to
disagree. Insite fills it from the **first Sales Order** on the scope. Not the
quotation. A quotation means nothing until it has been ordered, and plenty of
work is ordered over the phone with no quotation at all.

Only a blank is filled. Once a scope has a planned amount that is the agreed
baseline, and every later order on that scope is a variation measured against
it — which is what **Variance to Plan** reads. When the client signs a
change, edit the Planned Amount to the new contract value. Frappe keeps the
change history on the document.

A Scope Item is also an **Accounting Dimension**. Every sales and purchase line
can carry a Scope, so the cost and the revenue stay attached to the work.

**The scope belongs to the line, not to the item.** One item belongs to many
scopes at once. A door handle belongs to every scope that has doors, with a
different quantity and a different rate in each. So a document carries the same
item on several lines, each under its own scope. Install turns on ERPNext's
**Allow Item to Be Added Multiple Times in a Transaction** for exactly this
reason.

## What a scope has cost, and what it is about to cost

Revenue and cost both reach the ledger tagged with the Scope, so ERPNext can
report profit per scope without Insite adding anything. **Profitability
Analysis** does exactly that, and a scope can carry an ERPNext **Budget** the
way a cost centre can.

What no ledger holds is the **commitment**. A Purchase Order is a promise to pay
that has not been posted, so a scope reads as profitable right up to the moment
the supplier's invoices arrive. That is the quiet way a contract is lost: the
margin was spent months before anyone could see it.

So Insite separates three things:

| | What it is |
| --- | --- |
| **Cost** | posted to expense accounts against the scope |
| **Committed** | ordered from suppliers and not yet invoiced |
| **Expected Cost** | the two together — what the scope will have cost |

**Margin** is the Contract Value less the Expected Cost, which is the number to
manage a job by. **Scope Profitability** shows all of it, worst margin first,
life-to-date — a contract is not a fiscal year, and costing a scope over a
period while its contract value covers the whole job compares two different
things.

## Collecting a payment

A contractor is paid per job. A customer with three jobs running has open
invoices on all three, and allocating a receipt against the wrong one puts the
money on the wrong contract.

So the outstanding invoices a Payment Entry offers can be filtered by
**Project**, or by **Scope** to collect against one part of a job. A project is
matched on the invoice; a scope on its lines, because that is where a scope
lives — an invoice covering three scopes appears under all three. Allocation is
still per invoice. What the filters change is which invoices you choose among.

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

## Rejected work

The consultant rejects six panels on the third floor. That is a **Quality
Inspection** — ERPNext's own document, not one of Insite's.

It already holds everything the event needs: a status of Accepted, Rejected or
Cancelled, who inspected it, who verified it, the remarks and the readings. Both
Delivery Note Item and Sales Invoice Item already link to one. Insite adds the
two things it lacks for contracting:

| Field | Why |
| --- | --- |
| **Scope** | So the rejection reports against the right scope of work. It is filled in from the delivery line, so nobody types it twice. |
| **Rejected Qty** | An inspection is otherwise pass-or-fail for a whole line. `rejected_qty` exists only on Purchase Receipt Item, so there is no way to say six of a hundred and sixty-eight. Leave it blank to mean the whole line. |

From those, Insite works out the **Rejected Amount** using the rate on the line
the inspection came off. It is a management figure, not a ledger entry: nothing
here posts to an account.

For the item to be inspectable on the way out, tick **Inspection Required before
Delivery** on it. ERPNext refuses to create an outgoing inspection otherwise.

A submitted inspection still marked **Rejected** does two things:

- **It speaks up at billing time.** Invoicing that scope warns you and names the
  inspections. Turn on *Refuse to Submit Invoices for a Scope With Rejected
  Work* in Insite Settings to make that a hard stop on submit. A draft can
  always be saved, and a credit note is always allowed.
- **It shows in Contract Progress**, as **Rejected** beside Delivered, so the
  delivered figure never reads better than the site does.

Settling it is ERPNext's business, not Insite's: mark the inspection Accepted
once the work is redone, or raise a return and a credit note. Insite writes no
statuses and posts nothing.

**Buying needs nothing from us.** Purchase Receipt already has a rejected
quantity and a rejected warehouse, and the Scope field is already on those
lines, so a supplier's bad batch lands against the right scope on its own.

## Printing

Insite ships a print format for the quotation, the order, the delivery note and
the invoice. Each groups the lines by **Scope**, with a subtotal per scope, and
prints the measurement under every line: `H 1.500 × W 2.800 × 40 off`.

That line is what a client checks. A contractor bills a measured quantity, and
the argument is about the measurement, not the total. ERPNext's own formats show
neither the scope nor the dimensions, so this is the one place the model had to
be made visible on paper.

The markup lives in a single shared template. The four formats are thin records
that include it, so the table cannot drift between documents.

## How the pieces work together

1. You write the Measurement Rules once, and add a Measurement Field for any
   number Insite does not ship.
2. You create a Project and its Scope Items, with the planned amounts.
3. Your team quotes, orders, delivers and invoices as usual. Insite calculates
   the quantity of a measured line, writes any other numbers the rule produces,
   and keeps the line tied to its Scope.
4. When the scope changes, you raise another Sales Order against the same Scope
   Item. When work comes back rejected, you raise a Quality Inspection on the
   delivery line and Insite carries the Scope onto it.
5. **Contract Progress** shows, for each scope: planned, ordered, the variance
   to plan, delivered, what is rejected, invoiced, and what is left to invoice.
   **Measurement Register** shows what a scope is made of. **Scope
   Profitability** shows whether it will make money, commitments included.
6. You print the quotation or the invoice grouped by scope, with the
   measurements shown, and the client can check the arithmetic.
7. When the payment arrives, you filter the outstanding invoices to that job so
   the receipt lands on the right contract.
