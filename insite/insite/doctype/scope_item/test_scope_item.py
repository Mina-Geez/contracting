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


class TestMeasurementSummary(IntegrationTestCase):
	"""The plain-English rule summary, which read as raw tokens for a while
	because its word boundaries were literal backspace bytes."""

	def test_it_reads_in_the_words_on_the_form(self):
		from insite.insite.doctype.measurement_rule.measurement_rule import in_plain_words

		rows = [
			frappe._dict({"token": "height", "field_label": "Height", "source": "Line"}),
			frappe._dict({"token": "width", "field_label": "Width", "source": "Line"}),
			frappe._dict({"token": "count", "field_label": "Count", "source": "Line"}),
		]
		self.assertEqual(in_plain_words("height * width * count", rows), "Height × Width × Count")

	def test_a_name_inside_a_longer_name_is_left_alone(self):
		from insite.insite.doctype.measurement_rule.measurement_rule import in_plain_words

		rows = [
			frappe._dict({"token": "count", "field_label": "Count", "source": "Line"}),
			frappe._dict({"token": "panel_count", "field_label": "Panels", "source": "Line"}),
		]
		self.assertEqual(in_plain_words("panel_count * count", rows), "Panels × Count")

	def test_a_constant_reads_as_its_number(self):
		from insite.insite.doctype.measurement_rule.measurement_rule import in_plain_words

		rows = [
			frappe._dict({"token": "count", "field_label": "Count", "source": "Line"}),
			frappe._dict(
				{"token": "waste", "field_label": None, "source": "Constant", "constant_value": 1.12}
			),
		]
		self.assertEqual(in_plain_words("count * waste", rows), "Count × 1.12")
