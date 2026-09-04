"""Integration tests for the Scope axis — run on a bench, not with pytest.

	bench --site <site> run-tests --app insite

Rejected work is ERPNext's Quality Inspection, so these cover what Insite adds
to it: the Scope carried down from the delivery line, the value of what was
refused, and what an outstanding rejection does to billing and to Contract
Progress.
"""

import frappe
from frappe.tests import IntegrationTestCase

from insite.constants import QI_ACCEPTED, QI_REJECTED, QUALITY_INSPECTION

RATE = 3500.0
DELIVERED = 168.0


def _a_company() -> str:
	existing = frappe.get_all("Company", pluck="name")
	if existing:
		return existing[0]
	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": "Insite Test Company",
			"abbr": "ITC",
			"default_currency": "USD",
			"country": "United States",
		}
	)
	company.insert(ignore_permissions=True)
	return company.name


def _ensure(doctype: str, filters: dict, values: dict) -> str:
	"""Create a record once, looking it up by the field that is actually unique.

	Several of these doctypes are named by series — a Project is PROJ-0004, not
	its title — so checking `exists(doctype, title)` never matches and the
	second run dies on the unique constraint.
	"""
	existing = frappe.db.get_value(doctype, filters, "name")
	if existing:
		return existing
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.insert(ignore_permissions=True)
	return doc.name


class TestRejectedWork(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.customer = _ensure(
			"Customer",
			{"customer_name": "Insite Test Customer"},
			{"customer_name": "Insite Test Customer", "customer_type": "Company"},
		)
		cls.item = _ensure(
			"Item",
			{"item_code": "INSITE-TEST-GLASS"},
			{
				"item_code": "INSITE-TEST-GLASS",
				"item_name": "Insite Test Glass",
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
				"stock_uom": "Square Meter",
				"is_stock_item": 0,
				# ERPNext refuses an outgoing Quality Inspection unless the item
				# asks for one: "'Inspection Required before Delivery' has
				# disabled for the item … no need to create the QI".
				"inspection_required_before_delivery": 1,
			},
		)
		frappe.db.set_value("Item", cls.item, "inspection_required_before_delivery", 1)
		cls.project = _ensure(
			"Project",
			{"project_name": "Insite Test Project"},
			{"project_name": "Insite Test Project", "company": cls.company, "status": "Open"},
		)
		cls.scope = _ensure(
			"Scope Item",
			{"scope_title": "Curtain wall glazing", "project": cls.project},
			{
				"scope_title": "Curtain wall glazing",
				"project": cls.project,
				"status": "Active",
				"planned_amount": 600000,
			},
		)
		cls.other_company = _ensure(
			"Company",
			{"company_name": "Insite Other Company"},
			{
				"company_name": "Insite Other Company",
				"abbr": "IOC",
				"default_currency": "USD",
				"country": "United States",
			},
		)
		frappe.db.commit()

	def setUp(self):
		self.delivery = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"items": [
					{
						"item_code": self.item,
						"qty": DELIVERED,
						"rate": RATE,
						"scope_item": self.scope,
					}
				],
			}
		).insert()

	def tearDown(self):
		"""Committing the shared fixtures takes these tests outside Frappe's
		per-test rollback, so each has to clear up after itself."""
		frappe.db.delete(QUALITY_INSPECTION, {"scope_item": self.scope})
		frappe.db.commit()

	def _inspection(self, **overrides):
		values = {
			"doctype": QUALITY_INSPECTION,
			"inspection_type": "Outgoing",
			"reference_type": "Delivery Note",
			"reference_name": self.delivery.name,
			"child_row_reference": self.delivery.items[0].name,
			"item_code": self.item,
			"company": self.company,
			"status": QI_REJECTED,
			"sample_size": 1,  # mandatory on Quality Inspection
			"custom_rejected_qty": 5.8,
			# Built from a dict rather than new_doc, so Frappe's special "user"
			# default on this Link field is never resolved to the session user.
			"inspected_by": frappe.session.user,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	# --- what Insite adds to a Quality Inspection ----------------------------

	def test_the_scope_comes_down_from_the_delivery_line(self):
		"""Asking for it twice invites the two to disagree."""
		inspection = self._inspection()
		inspection.insert()
		self.assertEqual(inspection.scope_item, self.scope)

	def test_it_is_valued_from_the_rate_on_the_line(self):
		inspection = self._inspection()
		inspection.insert()
		self.assertAlmostEqual(inspection.custom_rejected_amount, 5.8 * RATE)

	def test_a_blank_quantity_means_the_whole_line(self):
		inspection = self._inspection(custom_rejected_qty=0)
		inspection.insert()
		self.assertAlmostEqual(inspection.custom_rejected_amount, DELIVERED * RATE)

	def test_more_rejected_than_delivered_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._inspection(custom_rejected_qty=DELIVERED + 1).insert()

	def test_an_accepted_inspection_is_worth_nothing(self):
		inspection = self._inspection(status=QI_ACCEPTED)
		inspection.insert()
		self.assertAlmostEqual(inspection.custom_rejected_amount, 0)

	def test_a_scope_from_another_company_is_refused(self):
		other_scope = _ensure(
			"Scope Item",
			{"scope_title": "Elsewhere", "project": self.project},
			{"scope_title": "Elsewhere", "project": self.project, "status": "Active"},
		)
		frappe.db.set_value("Scope Item", other_scope, "company", self.other_company)
		with self.assertRaises(frappe.ValidationError):
			self._inspection(scope_item=other_scope).insert()

	def test_the_same_item_under_two_scopes_is_not_settled_in_silence(self):
		"""A door handle belongs to every scope that has doors.

		When an inspection does not come off a line, ERPNext binds it to the
		first row matching the item code and says nothing. The rejection is then
		filed against one scope at that scope's rate when the other may have
		been meant. Insite cannot tell a deliberate choice from ERPNext's
		default, so it does not override — it says so.
		"""
		other_scope = _ensure(
			"Scope Item",
			{"scope_title": "Second floor glazing", "project": self.project},
			{"scope_title": "Second floor glazing", "project": self.project, "status": "Active"},
		)
		two_scopes = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"items": [
					{"item_code": self.item, "qty": 10, "rate": RATE, "scope_item": self.scope},
					{"item_code": self.item, "qty": 20, "rate": 1000, "scope_item": other_scope},
				],
			}
		).insert()

		before = len(frappe.message_log)
		inspection = self._inspection(
			reference_name=two_scopes.name, child_row_reference=None, custom_rejected_qty=2
		)
		inspection.insert()
		raised = str(frappe.message_log[before:])

		self.assertIn("Second floor glazing", raised)
		self.assertIn(str(two_scopes.items[1].idx), raised)

	# --- what rejected work does to the rest of the app ----------------------

	def test_contract_progress_totals_rejected_work(self):
		from insite.insite.report.contract_progress.contract_progress import execute

		self._inspection().submit()

		columns, rows = execute({"company": self.company, "project": self.project})
		self.assertIn("rejected_open", [c["fieldname"] for c in columns])
		row = next(r for r in rows if r["scope"] == self.scope)
		self.assertAlmostEqual(row["rejected_open"], 5.8 * RATE)

	def test_a_draft_inspection_is_not_counted(self):
		"""Nothing is rejected until somebody stands behind it."""
		from insite.insite.report.contract_progress.contract_progress import execute

		self._inspection().insert()  # draft, not submitted

		_, rows = execute({"company": self.company, "project": self.project})
		row = next(r for r in rows if r["scope"] == self.scope)
		self.assertAlmostEqual(row["rejected_open"], 0)

	def _invoice(self, **overrides):
		values = {
			"doctype": "Sales Invoice",
			"customer": self.customer,
			"company": self.company,
			"project": self.project,
			"items": [{"item_code": self.item, "qty": 1, "rate": 100, "scope_item": self.scope}],
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_the_invoice_guard_names_the_inspection(self):
		from insite.overrides.transaction import warn_open_rejections

		inspection = self._inspection()
		inspection.submit()

		before = len(frappe.message_log)
		warn_open_rejections(self._invoice())
		raised = frappe.message_log[before:]

		self.assertTrue(raised, "rejected work on the scope should warn")
		self.assertIn(inspection.name, str(raised[-1]))

	def test_a_credit_note_is_never_warned_about(self):
		from insite.overrides.transaction import warn_open_rejections

		self._inspection().submit()
		credit_note = self._invoice(
			is_return=1, items=[{"item_code": self.item, "qty": -1, "rate": 100, "scope_item": self.scope}]
		)

		before = len(frappe.message_log)
		warn_open_rejections(credit_note)
		self.assertEqual(len(frappe.message_log), before)

	def test_blocking_refuses_a_submit_but_never_a_draft(self):
		from insite.overrides.transaction import warn_open_rejections

		self._inspection().submit()
		frappe.db.set_single_value("Insite Settings", "block_invoicing_with_open_rejections", 1)
		try:
			invoice = self._invoice()

			# A draft is only ever warned about: someone has to be able to save
			# the invoice in front of them and settle the inspection after.
			invoice.docstatus = 0
			warn_open_rejections(invoice)

			# The refusal lands on submit, which is where the money is.
			invoice.docstatus = 1
			with self.assertRaises(frappe.ValidationError):
				warn_open_rejections(invoice)
		finally:
			frappe.db.set_single_value("Insite Settings", "block_invoicing_with_open_rejections", 0)


class TestThePlanFillsItself(IntegrationTestCase):
	"""A scope's Planned Amount comes from the first Sales Order on it.

	Nobody knows the value when they create the scope, and typing a number in
	two places is how two numbers come to disagree. The order is the
	commitment: a quotation means nothing until it has been ordered, and plenty
	of work is ordered over the phone with no quotation at all. Later orders on
	the scope are variations measured against the first.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.customer = _ensure(
			"Customer",
			{"customer_name": "Insite Plan Customer"},
			{"customer_name": "Insite Plan Customer", "customer_type": "Company"},
		)
		cls.item = _ensure(
			"Item",
			{"item_code": "INSITE-PLAN-ITEM"},
			{
				"item_code": "INSITE-PLAN-ITEM",
				"item_name": "Insite Plan Item",
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
			},
		)
		cls.project = _ensure(
			"Project",
			{"project_name": "Insite Plan Project"},
			{"project_name": "Insite Plan Project", "company": cls.company, "status": "Open"},
		)
		frappe.db.commit()

	def _scope(self):
		"""A scope with no planned amount, the way one is really created."""
		return (
			frappe.get_doc(
				{
					"doctype": "Scope Item",
					"scope_title": f"Plan {frappe.generate_hash(length=8)}",
					"project": self.project,
					"status": "Active",
				}
			)
			.insert()
			.name
		)

	def _order(self, scope, rate, qty=1, doctype="Sales Order"):
		doc = frappe.get_doc(
			{
				"doctype": doctype,
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"items": [{"item_code": self.item, "qty": qty, "rate": rate, "scope_item": scope}],
			}
		)
		if doctype == "Quotation":
			doc.quotation_to = "Customer"
			doc.party_name = self.customer
		else:
			doc.delivery_date = frappe.utils.add_days(frappe.utils.today(), 30)
		doc.insert()
		doc.submit()
		return doc

	def test_an_order_taken_by_phone_sets_the_plan(self):
		scope = self._scope()
		self.assertFalse(frappe.db.get_value("Scope Item", scope, "planned_amount"))

		self._order(scope, rate=5000)
		self.assertAlmostEqual(frappe.db.get_value("Scope Item", scope, "planned_amount"), 5000)

	def test_a_quotation_needs_neither_a_project_nor_a_scope(self):
		"""At quote time the job may not exist yet.

		Nothing is enforced until the Sales Order, and the line still measures.
		Both fields are there to be used when the job is already running — a
		Quotation has no Project of its own in ERPNext, so Insite adds one.
		"""
		quote = frappe.get_doc(
			{
				"doctype": "Quotation",
				"quotation_to": "Customer",
				"party_name": self.customer,
				"company": self.company,
				"items": [{"item_code": self.item, "qty": 3, "rate": 100}],
			}
		).insert()

		self.assertFalse(quote.get("project"))
		self.assertFalse(quote.items[0].get("scope_item"))
		self.assertEqual(quote.items[0].qty, 3)
		self.assertFalse(frappe.get_meta("Quotation").get_field("project").reqd)

	def test_a_quotation_alone_plans_nothing(self):
		"""A quotation means nothing until it has been ordered."""
		scope = self._scope()
		self._order(scope, rate=7500, doctype="Quotation")
		self.assertFalse(frappe.db.get_value("Scope Item", scope, "planned_amount"))

		# and the order that follows it is what sets the plan
		self._order(scope, rate=7500)
		self.assertAlmostEqual(frappe.db.get_value("Scope Item", scope, "planned_amount"), 7500)

	def test_a_later_order_is_a_variation_not_a_new_plan(self):
		"""The whole point: the baseline must hold still so variance can mean something."""
		scope = self._scope()
		self._order(scope, rate=5000)
		self._order(scope, rate=1200)  # the variation

		self.assertAlmostEqual(frappe.db.get_value("Scope Item", scope, "planned_amount"), 5000)

		from insite.insite.report.contract_progress.contract_progress import execute

		_, rows = execute({"company": self.company, "project": self.project})
		row = next(r for r in rows if r["scope"] == scope)
		self.assertAlmostEqual(row["planned"], 5000)
		self.assertAlmostEqual(row["ordered"], 6200)
		self.assertAlmostEqual(row["variance_to_plan"], 1200)

	def test_a_plan_somebody_agreed_is_never_overwritten(self):
		scope = self._scope()
		frappe.db.set_value("Scope Item", scope, "planned_amount", 999)
		self._order(scope, rate=5000)
		self.assertAlmostEqual(frappe.db.get_value("Scope Item", scope, "planned_amount"), 999)


class TestContractorJourney(IntegrationTestCase):
	"""Quotation to invoice, the way the app is meant to be used.

	This is the spine: a quote is measured and priced, it is approved, and the
	Sales Order, Delivery Note and Sales Invoice made from it all carry the
	measured quantity and the Scope through without anyone retyping either.

	It exists because that journey was broken and nothing noticed. ERPNext only
	puts Accounting Dimensions on doctypes that post to the ledger, so Quotation
	Item never had `scope_item`; Frappe silently dropped the value, and the
	Sales Order made from the quote was refused by Insite's own Scope check.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.customer = _ensure(
			"Customer",
			{"customer_name": "Insite Journey Customer"},
			{"customer_name": "Insite Journey Customer", "customer_type": "Company"},
		)
		cls.group = _ensure(
			"Item Group",
			{"item_group_name": "Insite Journey Glazing"},
			{
				"item_group_name": "Insite Journey Glazing",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			},
		)
		cls.item = _ensure(
			"Item",
			{"item_code": "INSITE-JOURNEY-GLASS"},
			{
				"item_code": "INSITE-JOURNEY-GLASS",
				"item_name": "Insite Journey Glass",
				"item_group": cls.group,
				"stock_uom": "Square Meter",
				"is_stock_item": 0,
			},
		)
		# The field is work_item_type_name; the doctype is autonamed from it.
		cls.work_item_type = _ensure(
			"Work Item Type",
			{"work_item_type_name": "Insite Journey Glass"},
			{"work_item_type_name": "Insite Journey Glass"},
		)
		if not frappe.db.exists("Measurement Rule", {"item_group": cls.group}):
			frappe.get_doc(
				{
					"doctype": "Measurement Rule",
					"work_item_type": cls.work_item_type,
					"apply_on": "Item Group",
					"item_group": cls.group,
					"preset": "Area",
					"inputs": [
						{"source": "Line", "field_name": "custom_height", "token": "height"},
						{"source": "Line", "field_name": "custom_width", "token": "width"},
						{"source": "Line", "field_name": "custom_base_qty", "token": "count"},
					],
					"formula": "height * width * count",
				}
			).insert(ignore_permissions=True)
		cls.project = _ensure(
			"Project",
			{"project_name": "Insite Journey Project"},
			{"project_name": "Insite Journey Project", "company": cls.company, "status": "Open"},
		)
		frappe.db.commit()

	def setUp(self):
		# A scope of its own each run, so the report totals this journey's
		# documents and not those of every run before it.
		self.scope = (
			frappe.get_doc(
				{
					"doctype": "Scope Item",
					"scope_title": f"Journey {frappe.generate_hash(length=8)}",
					"project": self.project,
					"status": "Active",
					"planned_amount": 600000,
				}
			)
			.insert()
			.name
		)

	def test_the_quantity_and_the_scope_survive_the_whole_journey(self):
		from erpnext.selling.doctype.quotation.quotation import make_sales_order
		from erpnext.selling.doctype.sales_order.sales_order import (
			make_delivery_note,
			make_sales_invoice,
		)

		from insite.insite.report.contract_progress.contract_progress import execute

		measured = 1.5 * 2.8 * 40  # 168

		quotation = frappe.get_doc(
			{
				"doctype": "Quotation",
				"quotation_to": "Customer",
				"party_name": self.customer,
				"company": self.company,
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"rate": 3500,
						"scope_item": self.scope,
						"custom_height": 1.5,
						"custom_width": 2.8,
						"custom_base_qty": 40,
					}
				],
			}
		).insert()

		# The server measured the line; the typed qty of 1 is gone.
		self.assertAlmostEqual(quotation.items[0].qty, measured)
		self.assertEqual(quotation.items[0].scope_item, self.scope)
		quotation.submit()

		order = make_sales_order(quotation.name)
		order.delivery_date = frappe.utils.add_days(frappe.utils.today(), 30)
		order.project = self.project
		order.insert()
		self.assertAlmostEqual(order.items[0].qty, measured)
		self.assertEqual(order.items[0].scope_item, self.scope, "the Scope must survive the mapping")
		order.submit()

		delivery = make_delivery_note(order.name)
		delivery.insert()
		self.assertAlmostEqual(delivery.items[0].qty, measured)
		self.assertEqual(delivery.items[0].scope_item, self.scope)
		delivery.submit()

		invoice = make_sales_invoice(order.name)
		invoice.insert()
		self.assertAlmostEqual(invoice.items[0].qty, measured)
		self.assertEqual(invoice.items[0].scope_item, self.scope)
		invoice.submit()

		_, rows = execute({"company": self.company, "project": self.project})
		row = next(r for r in rows if r["scope"] == self.scope)
		self.assertAlmostEqual(row["ordered"], measured * 3500)
		self.assertAlmostEqual(row["delivered"], measured * 3500)
		self.assertAlmostEqual(row["invoiced"], measured * 3500)
		self.assertAlmostEqual(row["pct_invoiced"], 100.0)
