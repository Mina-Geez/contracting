"""Integration tests for Rejection — run these on a bench, not with pytest.

	bench --site <site> run-tests --app insite

These cover the things the offline suite structurally cannot: that the document
saves against a real database, that each guard actually fires, that the invoice
warning reaches the message log, and that Contract Progress totals open
rejections without throwing. Every one of them was verified by hand on a live
site first; this is that verification made repeatable.
"""

import frappe
from frappe.tests import IntegrationTestCase

from insite.constants import REJECTION_CREDITED, REJECTION_OPEN, REJECTION_REWORKED


def _a_company() -> str:
	"""Whatever company this site has.

	A test site gets ERPNext's `_Test Company` from its own bootstrap; a site
	someone set up by hand has theirs. Either will do — these tests care about
	scopes and rejections, not about the chart of accounts.
	"""
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
	"""Create a record once, and hand back its name on every later run.

	The lookup is by field, not by name, because several of these doctypes are
	named by series: a Project is PROJ-0004, not "Insite Test Project". Checking
	`exists(doctype, title)` on those never matches, and the second run dies on
	the unique constraint instead.
	"""
	existing = frappe.db.get_value(doctype, filters, "name")
	if existing:
		return existing
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.insert(ignore_permissions=True)
	return doc.name


class TestRejection(IntegrationTestCase):
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
			},
		)
		cls.project = _ensure(
			"Project",
			{"project_name": "Insite Test Project"},
			{"project_name": "Insite Test Project", "company": cls.company, "status": "Open"},
		)
		cls.other_project = _ensure(
			"Project",
			{"project_name": "Insite Other Project"},
			{"project_name": "Insite Other Project", "company": cls.company, "status": "Open"},
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
		frappe.db.commit()

	def tearDown(self):
		"""Leave the scope with no rejections on it.

		Committing the fixtures above takes these tests outside the per-test
		rollback, so each one has to clear up after itself. Without this they
		pass alone and fail together: the report totals every rejection the
		earlier tests left behind, and the invoice warning — which names five
		and then says "and more" — stops naming the one the test just made.
		"""
		frappe.db.delete("Rejection", {"scope_item": self.scope})
		frappe.db.commit()

	def _rejection(self, **overrides):
		values = {
			"doctype": "Rejection",
			"project": self.project,
			"scope_item": self.scope,
			"item_code": self.item,
			"rejected_qty": 5.8,
			"rate": 3500,
			"reason": "Edge seal delaminated on two units.",
			"rejected_by": "Site consultant",
		}
		values.update(overrides)
		return frappe.get_doc(values)

	# --- the document itself -------------------------------------------------

	def test_it_values_itself_and_writes_its_own_title(self):
		rejection = self._rejection()
		rejection.insert()

		self.assertEqual(rejection.status, REJECTION_OPEN)
		self.assertAlmostEqual(rejection.rejected_amount, 5.8 * 3500)
		# The title is what a reader sees in every list and link.
		self.assertIn("Insite Test Glass", rejection.rejection_summary)
		self.assertIn("Curtain wall glazing", rejection.rejection_summary)
		self.assertIsNone(rejection.closed_on)

	def test_an_amount_may_be_entered_without_a_rate(self):
		"""Reporting a rejection must never be held up for want of a price."""
		rejection = self._rejection(rate=0, rejected_amount=1234)
		rejection.insert()
		self.assertAlmostEqual(rejection.rejected_amount, 1234)

	def test_nothing_rejected_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._rejection(rejected_qty=0).insert()

	def test_a_scope_from_another_project_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._rejection(project=self.other_project).insert()

	# --- closing -------------------------------------------------------------

	def test_credited_demands_the_credit_note(self):
		rejection = self._rejection()
		rejection.insert()
		rejection.status = REJECTION_CREDITED
		with self.assertRaises(frappe.ValidationError):
			rejection.save()

	def test_closing_stamps_the_date_and_reopening_clears_it(self):
		rejection = self._rejection()
		rejection.insert()

		rejection.status = REJECTION_REWORKED
		rejection.save()
		self.assertIsNotNone(rejection.closed_on)

		rejection.status = REJECTION_OPEN
		rejection.save()
		self.assertIsNone(rejection.closed_on)

	# --- what an open rejection does to the rest of the app ------------------

	def test_contract_progress_totals_open_rejections(self):
		from insite.insite.report.contract_progress.contract_progress import execute

		self._rejection().insert()

		columns, rows = execute({"company": self.company, "project": self.project})
		self.assertIn("rejected_open", [c["fieldname"] for c in columns])

		row = next(r for r in rows if r["scope"] == self.scope)
		self.assertAlmostEqual(row["rejected_open"], 5.8 * 3500)

	def test_a_closed_rejection_leaves_the_report_alone(self):
		from insite.insite.report.contract_progress.contract_progress import execute

		rejection = self._rejection()
		rejection.insert()
		rejection.status = REJECTION_REWORKED
		rejection.save()

		_, rows = execute({"company": self.company, "project": self.project})
		row = next(r for r in rows if r["scope"] == self.scope)
		self.assertAlmostEqual(row["rejected_open"], 0)

	def test_the_invoice_guard_speaks_up_and_names_the_rejection(self):
		from insite.overrides.transaction import warn_open_rejections

		rejection = self._rejection()
		rejection.insert()

		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"items": [{"item_code": self.item, "qty": 1, "rate": 100, "scope_item": self.scope}],
			}
		)

		before = len(frappe.message_log)
		warn_open_rejections(invoice)
		raised = frappe.message_log[before:]

		self.assertTrue(raised, "an open rejection on the scope should warn")
		self.assertIn(rejection.name, str(raised[-1]))

	def test_a_credit_note_is_never_warned_about(self):
		"""Raising one is how a rejection gets settled."""
		from insite.overrides.transaction import warn_open_rejections

		self._rejection().insert()
		credit_note = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"is_return": 1,
				"items": [{"item_code": self.item, "qty": -1, "rate": 100, "scope_item": self.scope}],
			}
		)

		before = len(frappe.message_log)
		warn_open_rejections(credit_note)
		self.assertEqual(len(frappe.message_log), before)

	def test_blocking_refuses_a_submit_but_never_a_draft(self):
		from insite.overrides.transaction import warn_open_rejections

		self._rejection().insert()
		frappe.db.set_single_value("Insite Settings", "block_invoicing_with_open_rejections", 1)
		try:
			invoice = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": self.customer,
					"company": self.company,
					"project": self.project,
					"items": [{"item_code": self.item, "qty": 1, "rate": 100, "scope_item": self.scope}],
				}
			)

			# A draft is only ever warned about: someone has to be able to save
			# the invoice in front of them and sort the rejection out after.
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
