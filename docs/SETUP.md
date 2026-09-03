# Insite setup guide

This guide takes you from a fresh install to a first job you can report on.
Read [CONCEPTS.md](./CONCEPTS.md) first if the words are new.

## 1. Install

```bash
bench get-app insite https://github.com/Mina-Geez/contracting --branch insite
bench --site <your-site> install-app insite
bench --site <your-site> migrate
```

Install adds, and re-adds on every migrate:

- the measurement fields on sales and purchase item rows;
- the **Scope** accounting dimension;
- the **Contracting Manager** role;
- the **Contracting Settings** single doctype.

Give the people who set up work and run contracts the **Contracting Manager**
role.

## 2. Set up a Work Item Type

Open **Insite > Work Item Type > New**.

1. Name it after the work, for example `Glass`.
2. Under **How is this measured?**, add a Measurement Rule:
   - **Applies To**: `Item Group`, then choose your glass item group.
   - **Measured By**: `area`.
3. Add default accounts per company if you want them.
4. Save.

Use **Test a Measure** on the form to check a rule before you rely on it. Enter
a sample height, width and count and read the result.

Repeat for each kind of work. A rule that uses `linear` needs a Length; one that
uses `piece_waste` needs a Count and a Wastage.

## 3. Create the job

1. Create a **Project** for the job.
2. Create a **Scope Item** for each scope of work. Give it a title, the project,
   and its **Planned Amount**. The code is assigned for you.

## 4. Quote, order, deliver, invoice

Work as usual in ERPNext. On each item row, fill in what you measured on site —
Height, Width, Length, Count, Wastage — and choose the **Scope**.

Insite calculates the quantity when you save. The typed quantity is replaced,
because the calculation is done on the server and cannot be edited around.

By default a Sales Order, Delivery Note or Sales Invoice must have a Project,
and a Scope on every measured line. Turn this off in **Contracting Settings** if
you do not want it.

## 5. Handle a change of scope

When the client changes the work:

1. Open **Variation Order > New**.
2. Choose the project, then add a line per affected scope with the amount added
   (positive) or removed (negative).
3. Submit it. The Scope Item's **Revised Amount** updates.

## 6. Read the progress

Open **Contract Progress**. Filter by company, project or status.

| Column | Meaning |
| --- | --- |
| Planned | baseline amount at award |
| Net Variations | total of approved changes |
| Revised | current contract value for the scope |
| Ordered | value on submitted Sales Orders |
| Delivered | value on submitted Delivery Notes |
| Invoiced | value on submitted Sales Invoices |
| Variance | Revised − Invoiced |
| Over-run | shown when ordered, delivered or invoiced is above Revised |

## Troubleshooting

**The quantity does not calculate.** No rule matched the item. Check that a Work
Item Type is enabled and that a rule covers the item or its item group.

**The quantity is not what I expect.** Open the row and read *Measure Used* and
*Work Item Type* under "Insite — Calculated". They name the rule that ran.

**I cannot save a Sales Order.** Add the Project, and a Scope on each measured
line. To switch the check off, clear **Require Project and Scope on Sales
Documents** in Contracting Settings.
