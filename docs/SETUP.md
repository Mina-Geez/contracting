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

- the measurement fields on the sales and purchase item rows
- the **Scope** accounting dimension
- the **Contracting Manager** role
- the **Contracting Settings** single doctype

Give the **Contracting Manager** role to the people who set up the work and run
the contracts.

## 2. Set up a Work Item Type

Open **Insite > Work Item Type > New**.

1. Name the type after the work, for example `Glass`.
2. Under **How is this measured?**, add a Measurement Rule.
3. Set **Applies To** to `Item Group`, then choose your glass item group.
4. Set **Measured By** to **Area (Height × Width × Count)**.
5. Add the default accounts per company that you want.
6. Save.

Use **Test a Measure** on the form to check a rule before you rely on it. Enter
a sample height, width and count, then read the result.

Repeat this for each kind of work. Each measure needs its own inputs.

| Measured By | Inputs it uses |
| --- | --- |
| Area (Height × Width × Count) | Height, Width, Count |
| Perimeter ((Height + Width) × 2 × Count) | Height, Width, Count |
| Linear (Length × Count) | Length, Count |
| Count | Count |
| Piece × Wastage (Count × Wastage) | Count, Wastage |
| Manual (keep the typed quantity) | none |
| Custom formula | the inputs your formula names |

## 3. Create the job

1. Create a **Project** for the job.
2. Create a **Scope Item** for each scope of work.
3. Give each Scope Item a **Title**, the **Project** and the **Planned Amount**.
   Insite assigns the code for you.

## 4. Quote, order, deliver, invoice

Work as usual in ERPNext. On each item row, open **Measurements** and
enter what you measured on site.

- **Height**, **Width** and **Length** — the site dimensions.
- **Count** — the number of units or pieces.
- **Wastage** — a multiplier, not a percentage. Type 1.1 to add 10 percent.
  Leave blank for none. A value of 10 gives ten times the quantity.
- **Scope** — the Scope Item that pays for this line.

Insite calculates the quantity when you save. The server does the calculation
and replaces the quantity you typed.

Insite asks a Sales Order, a Delivery Note and a Sales Invoice for a Project on
the header. It also asks for a Scope on each line that a Measurement Rule
matched. Insite does not check a line that no rule matched, so ordinary sales
still work. To switch the whole check off, clear **Require Project and Scope on
Sales Documents** in **Contracting Settings**.

## 5. Handle a change of scope

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

## 6. Read the progress

Open **Contract Progress**. Filter by company, project or status.

| Column | Meaning |
| --- | --- |
| Scope | the Scope Item |
| Status | the status of the Scope Item |
| Planned | the agreed baseline value of the scope |
| Ordered | value on submitted Sales Orders for this scope |
| Variance to Plan | Ordered − Planned |
| Delivered | value on submitted Delivery Notes |
| Invoiced | value on submitted Sales Invoices |
| Left to Invoice | Ordered − Invoiced |
| % Invoiced | Invoiced as a percentage of Ordered |

A change of scope is another Sales Order, so **Ordered** is the current
committed value of the work. **Variance to Plan** is how a change reads in the
report. Work ordered beyond the original plan shows as a positive number.

## 7. A worked example

A client orders six glass units. Each unit is 2.4 m high and 1.8 m wide. The
rate is 900 per square meter.

1. The Work Item Type `Glass` holds a rule on the glass item group. The rule
   uses **Area (Height × Width × Count)**.
2. Create the Scope Item `Curtain wall glazing` on the project. Set its
   **Planned Amount** to 25,000.
3. On the Sales Order line, enter Height 2.4, Width 1.8 and Count 6. Leave
   **Wastage** blank. Choose the Scope `Curtain wall glazing`.
4. Save. Insite writes a quantity of 25.92, because 2.4 × 1.8 × 6 = 25.92.
5. The line amount is 25.92 × 900 = 23,328.
6. Submit the Sales Order. **Contract Progress** shows Planned 25,000, Ordered
   23,328, Variance to Plan −1,672 and Left to Invoice 23,328.
7. Invoice the whole order. Invoiced becomes 23,328, % Invoiced reads 100, and
   Left to Invoice becomes 0.
8. The client now asks for two more units. Raise a second Sales Order on the
   same Project, and set the same Scope on the line.
9. Enter Height 2.4, Width 1.8 and Count 2. The quantity is 8.64, and the
   amount is 8.64 × 900 = 7,776.
10. Submit the second order. Ordered becomes 31,104, and Variance to Plan
    becomes +6,104. Left to Invoice becomes 7,776. That positive variance is
    the change of scope.
11. When the client signs the change, set the **Planned Amount** of the scope to
    31,104. Variance to Plan returns to zero.

To bill a 10 percent cutting allowance on the same line, type 1.1 in
**Wastage** and add the formula `height * width * count * wastage` to a Custom
formula rule. The quantity becomes 28.512.

## 8. Change a Measurement Rule later

A change to a Work Item Type or a Measurement Rule does not touch the documents
you already have. Insite calculates a quantity only when a person saves a
document. Past quotations, orders, deliveries and invoices keep the quantities
they hold. Submitted documents do not move.

To apply a new rule to an open draft, open the draft and save it again.

## 9. Who does what

| Role | What they do |
| --- | --- |
| Contracting Manager | Sets up Work Item Types and Measurement Rules. Creates and edits Scope Items, and sets the Planned Amount. Reads Contract Progress. |
| Sales User | Reads Scope Items. Enters the measurements and the Scope on quotations, sales orders and delivery notes. Reads Contract Progress. |
| Purchase User | Enters the measurements and the Scope on purchase documents. |
| Accounts User | Reads Scope Items. Enters the measurements and the Scope on invoices. Reads Contract Progress. |

## Troubleshooting

**The quantity does not calculate.** No rule matched the item. Check that a
Work Item Type is enabled, and that a rule covers the item or its item group.

**The quantity is ten times too big.** Read the **Wastage** on the line. Wastage
is a multiplier. Type 1.1 to add 10 percent, and leave the field blank for none.

**The quantity is not what I expect.** Open the row and read **Measure Used**
and **Work Item Type** under **Calculated**. They name the rule that
ran.

**I cannot save a Sales Order.** Add the Project, and add a Scope on each line
that a rule matched. To switch the check off, clear **Require Project and Scope
on Sales Documents** in Contracting Settings.
