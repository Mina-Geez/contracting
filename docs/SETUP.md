# Insite setup guide

This guide takes you from a fresh install to a first job you can report on.
Read [CONCEPTS.md](./CONCEPTS.md) first if the words are new.

## 1. Install

```bash
bench get-app insite https://github.com/Mina-Geez/contracting --branch insite
bench --site <your-site> install-app insite
bench --site <your-site> migrate
```

Install adds these items, and adds them again on every migrate:

- the measurement boxes on the sales and purchase item rows
- the **Scope** accounting dimension, and an index on it wherever the report
  reads it
- the **Contracting Manager** role
- the **Insite Settings** record
- the four Insite print formats
- every **Measurement Field** your site has added

Install also turns on **Allow Item to Be Added Multiple Times in a
Transaction** in Selling Settings. One item belongs to many scopes at once. A
door handle belongs to every scope that has doors, at a different rate in each.
Insite puts a scope on each line, so a document must be able to carry the same
item more than once. ERPNext refuses that by default. Insite never turns the
setting back off.

Give the **Contracting Manager** role to the people who set up the work and run
the contracts.

## 2. Add a Measurement Rule

This is the only thing to set up before you start. Open
**Insite > Measurement Rule > New**.

1. Set **Applies To** to `Item Group`, then choose your glass item group.
2. Set **Start from** to **Area**.
3. Read **Worked out as**. It says `Height × Width × Count`.
4. Save. Insite names the rule after what it applies to. Type a **Title** of
   your own if you would rather, and it keeps it.
5. Choose **Try it**. Enter sample numbers, then read the quantity.

Most rules need nothing more than those five steps.

**Start from** offers these starting points.

| Start from | What it works out |
| --- | --- |
| Area | Height × Width × Count |
| Perimeter | (Height + Width) × 2 × Count |
| Linear | Length × Count |
| Count | Count |
| Piece × Wastage | Count × Wastage |
| Volume | Height × Width × Length × Count |

Two more choices sit in the same list. **Manual** tells Insite never to
calculate the line, and to keep the quantity you typed. **Custom** is for a
formula you write from scratch.

Add a rule for each item group, brand, item, template or attribute value you
measure.

**You can also write the rule from the thing it measures.** Open an **Item
Group**, a **Brand** or an **Item**. The top of the form says which rule
measures it and how that rule works out, with a button to open it. Where nothing
does, it says so and offers **Measure This** — pick a starting point, and the
rule is written and pointed at the record you were standing on. Being there is
what said what it applies to, so it is not asked again.

A rule inherited from a parent item group names the group it was set on, so
nobody edits the wrong record. A record that already has a rule is not given a
second one — two rules on one target is a tie broken by priority, which is not
what the button meant. When two rules match the same item the narrower one wins, in the order
ERPNext already uses on the Item: item, then template, then attribute value,
then brand, then item group. A rule on an item group also covers the groups
beneath it, so one rule on a parent group can cover a whole branch.

### Adjust the measurement

**Adjust the measurement** is folded away on the form. Open it only when the
ready-made answer is not what you measure. It holds the **Inputs** and the
**Formula** behind the **Worked out as** line.

Each row of **Inputs** is one number the formula reads. **Comes from** says
where that number is.

| Comes from | Where the number is | Example |
| --- | --- | --- |
| Line | measured on the document | the height of this unit |
| Item | held on the material | the sheet the part is cut from |
| Constant | carried by the rule | a cutting allowance of 1.12 |

For **Line** and **Item**, pick the field from the list. You never type a field
name. For **Constant**, type the number in **Value**.

If the number you need is not in the list, choose **Add a new field…** at the
bottom of it. Give it a label and it is created, added to the documents, and
put into the row you were filling in — without leaving the half-written rule.
Insite works out where it belongs from **Comes from**: a `Line` input becomes a
box on every transaction line, an `Item` input a field on the Item. Section 4
covers the same thing from the other end, and says how to hide or remove one.

Each row also gives the number a short name for the formula. Insite suggests the
name from the label of the field. Keep it, or type a shorter one.

To read a sheet size from the material rather than from the line:

1. Add a row to **Inputs**.
2. Set **Comes from** to `Item`.
3. Pick the field, for example **Sheet Length**, from the list.
4. Use the name of that row in the **Formula**.
5. Save, then choose **Try it**.

Section 3 says how to add a number such as **Sheet Length** to the Item.

### What else these measurements give you

A rule can produce more than one number. Open this second folded-away section to
write further numbers onto the line from the same measurements. For a door: the
board it consumes, the edging round it, the fittings that go on it.

1. Add a row.
2. Pick the field the number is written to.
3. Write a **Formula** over the same input names.
4. Save.

The quantity stays what you bill. Insite writes the other numbers beside it when
someone saves the document.

A rule may not write to a field it reads. A rule may not write to the same field
twice. Insite refuses both when you save the rule.

## 3. Add a number of your own

Insite ships five measurement boxes: Count, Height, Width, Length and Wastage.
Add a **Measurement Field** for any other number your site measures.

The quickest way is not this form at all: while writing a Measurement Rule,
choose **Add a new field…** at the bottom of the field list. Use this form when
you are setting several up at once, or to change or hide one.

Open **Insite > Measurement Field > New**.

1. Type the **Label**, for example `Number of Panels`.
2. Set **Where it belongs**.
3. Write **Help Text** if the box needs it.
4. Save.

| Where it belongs | Use it for | Example |
| --- | --- | --- |
| Transaction line | a number measured each time | a panel count |
| Item | a number that is true of the material | the sheet it is cut from |

Insite adds the field everywhere it is needed, and adds it again on every
migrate. A rule then reads it like any other number. To measure by panels, point
a rule at **Number of Panels** and write `height * width * number_of_panels`.

**Used by rules** lists the rules that read the field. A field a rule uses cannot
be deleted. To take the box off the documents and keep everything already entered
in it, tick **Hide on documents**.

The site keeps the number and the label its people already know. Insite fits the
site, and the site does not fit Insite.

## 4. Create the job

1. Create a **Project** for the job.
2. Open it, and choose **Insite > Add Scopes**.
3. Type the scopes, one per line. Insite creates one Scope Item for each and
   assigns the codes. A title already on the project is left alone rather than
   duplicated, and it tells you which.

Create them one at a time from the **Scope Item** list if you prefer.

Leave the **Planned Amount** empty. Insite fills it in from the first **Sales
Order** on the scope, because the order is the commitment. A quotation does not
set it. After that it holds still, and later orders on the scope read as
**Variance to Plan**. Edit it when a change is formally agreed.

## 5. Quote, order, deliver, invoice

Work as usual in ERPNext. On each item row, open **Measurements** and enter what
you measured on site. The row shows only the boxes its rule reads.

- **Height**, **Width** and **Length** — the site dimensions.
- **Count** — the number of units or pieces.
- **Wastage** — a multiplier, not a percentage. Type 1.1 to add 10 percent.
  Leave blank for none. A value of 10 gives ten times the quantity.
- **Scope** — the Scope Item that pays for this line. The list offers only the
  scopes on the project of this document. A new line takes the Scope from the
  line above it.

The quantity and the amount follow the numbers as you type them. Insite works the
quantity out again on the server when you save, and that answer is the one you
keep. When every field the rule reads is empty, Insite leaves your quantity
alone.

### What the two pickers offer

Neither list ever offers something the document would be refused for.

| Picker | Offers |
| --- | --- |
| **Project**, on the header | jobs for this customer, plus any job with no customer set. ERPNext does not make that field mandatory, so a site that leaves it blank still gets a usable list. |
| **Scope**, on each line | scopes on this document's project, and nothing else |

The Project narrows only when the document is for a customer. A **Quotation** to
a Lead or a Prospect is offered every project, because a lead has no jobs of its
own yet.

Insite calculates on the Quotation, the Sales Order, the Delivery Note and the
Sales Invoice. Purchase documents carry the **Scope** for cost. Insite does not
calculate their quantities.

A **Quotation** asks for neither a Project nor a Scope. At quote time the job
may not exist yet. Both are there if you want them — Insite adds a Project to
the quotation header, which ERPNext does not have — and setting the Project
narrows the Scope list on the lines. Whatever you set carries to the Sales
Order.

Insite asks a Sales Order, a Delivery Note and a Sales Invoice for a Project on
the header. It also asks for a Scope on each line that a Measurement Rule
matched. Insite does not check a line that no rule matched, so ordinary sales
still work. To switch the whole check off, clear **Require Project and Scope on
Sales Documents** in **Insite Settings**.

## 6. Handle a change of scope

Insite has no change document. You raise another Sales Order against the same
scope, the way many contractors already work.

1. Agree the change with the client.
2. Create a **Sales Order** on the same **Project** as the original order.
3. Enter the extra work on the lines. Set the **Scope** on each line to the same
   Scope Item.
4. Submit the order. **Ordered** rises in **Contract Progress**, and **Variance
   to Plan** rises with it.
5. For work the client takes out, use the standard ERPNext route. Raise a credit
   note or a return, or raise the follow-on order for the reduced amount.
6. When the client signs the change, open the **Scope Item** and set the
   **Planned Amount** to the new contract value.

Step 6 is optional. It moves the baseline to the new contract value, so
**Variance to Plan** returns to zero. Frappe keeps the change history on the
Scope Item. Leave the Planned Amount alone to keep the original baseline in
view.

## 7. Collect a payment for one job

A contractor is paid per job, but a customer with three jobs running has open
invoices on all three. Allocating a receipt against the wrong one puts the money
on the wrong contract, and it is a quiet mistake to make.

1. Open a **Payment Entry** and choose the customer.
2. Choose **Get Outstanding Invoices**.
3. In the **Filters** dialog, set **Project** — or **Scope**, to collect against
   one part of a job.
4. Only that job's invoices are pulled in.

Both filters sit beside ERPNext's own — the posting and due dates, the
outstanding amount, and the Cost Center. Leave them empty and you get every open
invoice for the customer, exactly as before.

**Project** matches the invoice. **Scope** matches its lines, because that is
where a scope lives: an invoice covering three scopes appears under all three.
Allocation is still per invoice, so what these filters change is which invoices
you are choosing among, not how a payment is split.

## 8. Handle rejected work

The consultant rejects six of the panels you installed. Record it, so nobody
invoices them and nobody forgets to redo them.

Rejected work is ERPNext's **Quality Inspection**. Insite does not add a
document of its own. It adds a Scope and a quantity to that one.

**Once, on the item:** tick **Inspection Required before Delivery**. ERPNext
refuses to create an outgoing inspection for an item that does not ask for one.

Then, when work comes back:

1. From the **Delivery Note** the work went out on, create a **Quality
   Inspection** on the line — ERPNext offers this from the item row.
2. Set **Status** to `Rejected` and write the **Remarks**.
3. Enter **Rejected Qty** — how much of the line was refused. Leave it blank if
   the whole line was.
4. Submit it.

The **Scope** is filled in from the delivery line, and **Rejected Amount** is
worked out from the rate on that line. Both are read-only to you. Insite fills
them in so the two can never disagree.

While a submitted inspection is still `Rejected`:

- Invoicing that scope warns you and names the inspections. To make that a
  refusal instead, tick **Refuse to Submit Invoices for a Scope With Rejected
  Work** in **Insite Settings**. The refusal lands on submit — a draft can
  always be saved. Credit notes are always allowed.
- The value shows as **Rejected** in Contract Progress.

**Settling it is ERPNext's business.** Mark the inspection `Accepted` once the
work has been redone, or raise a return and a credit note the normal way. Insite
writes no statuses and posts nothing to the ledger.

**Rejecting a supplier's delivery needs none of this.** Use the **Rejected Qty**
on the Purchase Receipt, which ERPNext already has. The Scope on the line carries
the cost to the right place on its own.

## 9. Print it for the client

Insite ships four print formats: **Insite Quotation**, **Insite Sales Order**,
**Insite Delivery Note** and **Insite Sales Invoice**.

Open the document, choose the format from the print view, and it prints:

- the lines **grouped by Scope**, with a subtotal for each scope
- the **measurement under every line** — `H 1.500 × W 2.800 × 40 off` — showing
  only the boxes that were filled in
- lines with no scope last, under **Other**

That measurement line is the point. A client checks how the quantity was
arrived at, not the total.

To make one the default for a document type, set it as the **Default Print
Format** on that DocType, or pick it each time from the print view.

## 10. Read the progress

Open **Contract Progress**. Filter by company, customer, project or status.

**Filtering by customer** works on all three Insite reports, and means the same
thing in each: the scopes on that customer's projects. Choosing a customer also
narrows the Project list to their jobs, so the two filters cannot contradict
each other.

It reads the **Customer** on the Project — the same field ERPNext uses to narrow
the project picker on a sales document. A project with no customer set belongs
to nobody, so it is left out rather than shown under every customer. If a
customer filter comes back empty, that field is the first thing to check.

| Column | Meaning |
| --- | --- |
| Scope | the Scope Item |
| Status | the status of the Scope Item |
| Planned | the agreed baseline value of the scope |
| Ordered | value on submitted Sales Orders for this scope |
| Variance to Plan | Ordered − Planned |
| Delivered | value on submitted Delivery Notes |
| Rejected | value of submitted Quality Inspections still marked Rejected on this scope |
| Invoiced | value on submitted Sales Invoices |
| Left to Invoice | the committed value − Invoiced |
| % Invoiced | Invoiced as a percentage of the committed value |

**Rejected** is not netted off any other column. It is a claim against
work already delivered, not a ledger entry, so Delivered still says what went out
and Left to Invoice still says what is owed to you — reworked work is work you
will be paid for.

The committed value is Ordered. Before the first Sales Order, Ordered is zero, so
Contract Progress uses Planned as the committed value instead.

A change of scope is another Sales Order, so **Ordered** is the current committed
value of the work. **Variance to Plan** is how a change reads in the report. Work
ordered beyond the original plan shows as a positive number.

## 11. See what a scope is made of

**Contract Progress** says where a scope stands. **Measurement Register** says
what it is made of: every submitted line against the scope, the measurement
behind its quantity, and the specification that was on the item at the time.

Filter it by customer, project, scope, document type or date.

That last column answers the argument that starts when a developer changes a
standard mid-job. Which deliveries were made to the old one? Every line keeps
its own copy of the description from the moment it was raised, so editing the
Item now cannot rewrite what a past delivery says it supplied. Nothing has to be
switched on for this. The record was always there.

## 12. See whether it is making money

Open **Scope Profitability**. One row per scope, worst margin first. Filter by
company, customer, project or status.

| Column | Meaning |
| --- | --- |
| Contract Value | value on submitted Sales Orders — the job as sold, variations included |
| Revenue | posted to income accounts against this scope |
| Cost | posted to expense accounts against this scope |
| Committed | ordered from suppliers on submitted Purchase Orders, not yet invoiced |
| Expected Cost | Cost + Committed |
| Margin | Contract Value − Expected Cost |
| Margin % | Margin as a percentage of Contract Value |

**Committed is the column that earns this report.** A Purchase Order has not
reached the ledger, so every financial report in ERPNext shows a scope as
profitable until the supplier invoices arrive. A scope with 588,000 sold and
260,000 already on order is running at 56%, not at 100%.

Two things work differently from the accounting reports, on purpose:

- **No date range.** A contract is not a fiscal year. Costing a scope over a
  period while its contract value covers the whole job compares two different
  things, so every figure is life-to-date.
- **Worst first.** A report you open to control a job should open on the job that
  needs controlling.

### What ERPNext already does per scope

Insite registers the Scope as an **accounting dimension**, so ERPNext's own
reports work per scope with nothing more to install. Do not rebuild these:

| Report | What it answers |
| --- | --- |
| **Profitability Analysis** | income, expense and gross profit per scope, from the ledger — set *Based On* to `Accounting Dimension` and *Accounting Dimension* to `Scope` |
| **Budget Variance Report** | actual against a budget per scope |
| **Profit and Loss Statement** | the full P&L, filtered to one scope |
| **General Ledger** | every entry behind a scope's figures |

To set a cost budget for a scope, create a **Budget** with *Budget Against* set
to `Scope Item`. ERPNext will then warn or stop when spending runs past it,
exactly as it does for a cost centre.

Both **Profitability Analysis** and **Budget Variance Report** sit on the Insite
workspace so nobody has to know they were already there.

## 13. A worked example

A client orders six glass units. Each unit is 2.4 m high and 1.8 m wide. The
rate is 900 per square meter. The workshop also wants to know how much sheet the
order eats, at a 12 percent cutting allowance.

1. Add a **Measurement Field** called `Sheet Area`. Set **Where it belongs** to
   `Transaction line`.
2. Add one rule on the glass item group. Set
   **Start from** to **Area**. **Worked out as** reads
   `Height × Width × Count`.
3. Open **What else these measurements give you**. Add a row that writes to
   **Sheet Area**, with the formula `height * width * count * 1.12`.
4. Save the rule.
5. Create the Scope Item `Curtain wall glazing` on the project. Set its
   **Planned Amount** to 25,000.
6. On the Sales Order line, enter Height 2.4, Width 1.8 and Count 6. Choose the
   Scope `Curtain wall glazing`.
7. Save. Insite writes a quantity of 25.92, because 2.4 × 1.8 × 6 = 25.92. It
   writes **Sheet Area** from the same measurements: 25.92 × 1.12 = 29.0304.
8. The line amount is 25.92 × 900 = 23,328. The sheet area is not billed.
9. Submit the Sales Order. **Contract Progress** shows Planned 25,000, Ordered
   23,328, Variance to Plan −1,672 and Left to Invoice 23,328.
10. Invoice the whole order. Invoiced becomes 23,328, % Invoiced reads 100, and
    Left to Invoice becomes 0.
11. The client now asks for two more units. Raise a second Sales Order on the
    same Project, and set the same Scope on the line.
12. Enter Height 2.4, Width 1.8 and Count 2. The quantity is 8.64, and the
    amount is 8.64 × 900 = 7,776.
13. Submit the second order. Ordered becomes 31,104, and Variance to Plan
    becomes +6,104. Left to Invoice becomes 7,776. That positive variance is
    the change of scope.
14. When the client signs the change, set the **Planned Amount** of the scope to
    31,104. Variance to Plan returns to zero.

To bill the cutting allowance instead of only recording it, move it into the
quantity. Open **Adjust the measurement** on the rule. Add an input, set **Comes
from** to `Constant`, type 1.12 in **Value**, and name it `cutting_allowance`.
Change the formula to `height * width * count * cutting_allowance`. **Worked out
as** then reads `Height × Width × Count × 1.12`, and the quantity of the first
line becomes 29.03.

## 14. Change a Measurement Rule later

A change to a Measurement Rule does not touch the documents
you already have. Insite calculates a quantity only when a person saves a
document. Past quotations, orders, deliveries and invoices keep the quantities
they hold. Submitted documents do not move.

To apply a new rule to an open draft, open the draft and save it again.

## 15. Who does what

| Role | What they do |
| --- | --- |
| Contracting Manager | Sets up Measurement Rules and Measurement Fields. Creates and edits Scope Items, and sets the Planned Amount. Edits Insite Settings. Reads Contract Progress. |
| Sales User | Reads Scope Items. Enters the measurements and the Scope on quotations, sales orders and delivery notes. Reads Contract Progress. |
| Accounts User | Reads Scope Items. Enters the measurements and the Scope on invoices. Reads Contract Progress. |
| Purchase User | Reads Scope Items. Sets the Scope on purchase documents. |

## Troubleshooting

**The quantity does not calculate.** No rule matched the item, or nothing was
measured. Check that the rule is enabled, and that it covers the
item or its item group. Check that the rule is not disabled. Insite leaves the
line alone when every field the rule reads is empty.

**The quantity is ten times too big.** Read the **Wastage** on the line. Wastage
is a multiplier. Type 1.1 to add 10 percent, and leave the field blank for none.

**The quantity is not what I expect.** Open the row and read **Rule Used** and
**Measured By** under **Calculated**. They name the rule that ran and the
kind of work. Open that rule and read **Worked out as**.

**Insite says a line is no longer measured.** No rule matches that item any
more. Insite cleared what it wrote and left the quantity as it is. Check the
quantity, then add a rule for the item or type the quantity you want.

**A box I expect is missing from the line.** A line shows only the measurement
boxes its rule reads. Open the rule and read its **Inputs**.

**The field I want is not in the rule's list.** The list holds Insite's five
measurement boxes and every Measurement Field your site has added. Insite leaves
out the standard ERPNext numbers, such as rate and amount. To measure by a
number of your own, add a Measurement Field first. See section 3.

**I cannot delete a Measurement Field.** A rule reads it. **Used by rules** names
the rules. Change those rules first, or tick **Hide on documents** instead.

**Insite warns about rejected work when I save an invoice.** That scope has
submitted Quality Inspections still marked Rejected, and the message names them.
Mark each one Accepted once the work is redone, or invoice only what was
accepted. A credit note never triggers the warning.

**Insite will not let me submit an invoice over rejected work.** Someone has
ticked **Refuse to Submit Invoices for a Scope With Rejected Work** in **Insite
Settings**. Settle the inspection, or clear that setting to get a warning
instead. The draft still saves.

**ERPNext will not let me create a Quality Inspection.** The item does not ask
for one. Tick **Inspection Required before Delivery** on it.

**A Quality Inspection has no Scope on it.** Insite copies the Scope from the
delivery line it references. An inspection created without a reference to a line
has nothing to copy from — set the Scope by hand, or make it from the line.

**I cannot save a Sales Order.** Add the Project, and add a Scope on each line
that a rule matched. The Scope must belong to the same project and the same
company as the document. To switch the check off, clear **Require Project and
Scope on Sales Documents** in Insite Settings.
