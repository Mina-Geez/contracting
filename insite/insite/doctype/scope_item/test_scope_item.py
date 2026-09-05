"""Integration tests for the Scope axis — run on a bench, not with pytest.

	bench --site <site> run-tests --app insite

Rejected work is ERPNext's Quality Inspection, so these cover what Insite adds
to it: the Scope carried down from the delivery line, the value of what was
refused, and what an outstanding rejection does to billing and to Contract
Progress.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

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


class TestAddingScopesInOneGo(IntegrationTestCase):
	"""A job has six or ten scopes and a form each is the dullest part of setup."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.project = _ensure(
			"Project",
			{"project_name": "Insite Bulk Project"},
			{"project_name": "Insite Bulk Project", "company": cls.company, "status": "Open"},
		)
		frappe.db.commit()

	def tearDown(self):
		frappe.db.delete("Scope Item", {"project": self.project})
		frappe.db.commit()

	def test_a_list_of_titles_becomes_a_list_of_scopes(self):
		from insite.api import add_scopes

		result = add_scopes(self.project, "Curtain wall glazing\nACP cladding\nHandrails")

		self.assertEqual(len(result["created"]), 3)
		titles = frappe.get_all("Scope Item", filters={"project": self.project}, pluck="scope_title")
		self.assertEqual(sorted(titles), ["ACP cladding", "Curtain wall glazing", "Handrails"])

	def test_blank_lines_and_stray_spaces_are_ignored(self):
		from insite.api import add_scopes

		result = add_scopes(self.project, "  Glazing  \n\n\n   \nCladding\n")
		self.assertEqual(len(result["created"]), 2)
		titles = frappe.get_all("Scope Item", filters={"project": self.project}, pluck="scope_title")
		self.assertEqual(sorted(titles), ["Cladding", "Glazing"])

	def test_a_scope_already_on_the_project_is_left_alone(self):
		"""Two scopes with one name would split the work across two report rows."""
		from insite.api import add_scopes

		add_scopes(self.project, "Glazing")
		result = add_scopes(self.project, "glazing\nCladding")

		self.assertEqual(result["already_there"], ["glazing"])
		self.assertEqual(len(result["created"]), 1)
		self.assertEqual(frappe.db.count("Scope Item", {"project": self.project}), 2)

	def test_an_empty_list_is_refused(self):
		from insite.api import add_scopes

		with self.assertRaises(frappe.ValidationError):
			add_scopes(self.project, "   \n\n  ")


class TestTheMeasurementRegister(IntegrationTestCase):
	"""What a scope is actually made of, and to which specification.

	Its own item, because the rejection fixtures use one that ERPNext will not
	let out of the door without a Quality Inspection.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.customer = _ensure(
			"Customer",
			{"customer_name": "Insite Register Customer"},
			{"customer_name": "Insite Register Customer", "customer_type": "Company"},
		)
		cls.item = _ensure(
			"Item",
			{"item_code": "INSITE-REGISTER-ITEM"},
			{
				"item_code": "INSITE-REGISTER-ITEM",
				"item_name": "Insite Register Item",
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
			},
		)
		cls.project = _ensure(
			"Project",
			{"project_name": "Insite Register Project"},
			{"project_name": "Insite Register Project", "company": cls.company, "status": "Open"},
		)
		frappe.db.commit()

	def setUp(self):
		self.scope = (
			frappe.get_doc(
				{
					"doctype": "Scope Item",
					"scope_title": f"Register {frappe.generate_hash(length=8)}",
					"project": self.project,
					"status": "Active",
				}
			)
			.insert()
			.name
		)

	def test_it_shows_the_specification_that_was_supplied(self):
		"""The answer to 'which deliveries were made to the old standard'.

		Nothing new is recorded to answer it. Every line keeps its own copy of
		the description from the moment it was raised, so changing the Item
		later cannot rewrite what a past delivery says it supplied.
		"""
		from insite.insite.report.measurement_register.measurement_register import execute

		spec = "Handle type A, satin stainless, 300mm"
		delivery = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"items": [
					{
						"item_code": self.item,
						"qty": 12,
						"rate": 250,
						"scope_item": self.scope,
						"description": spec,
					}
				],
			}
		).insert()
		delivery.submit()

		_, rows = execute({"company": self.company, "project": self.project})
		mine = next(r for r in rows if r["document"] == delivery.name)

		self.assertEqual(mine["scope"], self.scope)
		self.assertEqual(mine["description"], spec)
		self.assertAlmostEqual(mine["qty"], 12)

		# Changing the item now must not rewrite what was already supplied.
		frappe.db.set_value("Item", self.item, "description", "Handle type B")
		_, rows = execute({"company": self.company, "project": self.project})
		still = next(r for r in rows if r["document"] == delivery.name)
		self.assertEqual(still["description"], spec)

	def test_a_draft_is_not_in_the_register(self):
		"""Nothing is supplied until it is submitted."""
		from insite.insite.report.measurement_register.measurement_register import execute

		draft = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"items": [{"item_code": self.item, "qty": 5, "rate": 100, "scope_item": self.scope}],
			}
		).insert()

		_, rows = execute({"company": self.company, "project": self.project})
		self.assertFalse([r for r in rows if r["document"] == draft.name])


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

	def test_an_order_in_another_currency_is_announced_in_ours(self):
		"""The plan is stored from `base_amount`, so it is in the company's currency.

		The message announcing it was formatted with the *document's* currency.
		An order of 1,000 of a foreign currency at rate 50 stored 50,000 and then
		told the user the scope was planned at 50,000 of the foreign one — fifty
		times the real figure, in the wrong money.
		"""
		home = frappe.get_cached_value("Company", self.company, "default_currency")
		others = [c for c in frappe.get_all("Currency", pluck="name") if c != home]
		if not others:
			self.skipTest("this site has one currency")

		scope = self._scope()
		order = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"currency": others[0],
				"conversion_rate": 50,
				"plc_conversion_rate": 50,
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 30),
				"items": [{"item_code": self.item, "qty": 10, "rate": 100, "scope_item": scope}],
			}
		)
		order.insert()
		frappe.clear_messages()
		order.submit()

		self.assertAlmostEqual(frappe.db.get_value("Scope Item", scope, "planned_amount"), 50_000)
		said = " ".join(str(entry) for entry in frappe.get_message_log())
		self.assertIn(frappe.utils.fmt_money(50_000, currency=home), said)

	def test_the_scope_is_locked_before_the_plan_is_read(self):
		"""Two orders submitted at the same moment must not both fill the plan.

		Read-then-write is a race: both see a blank plan, both write, and the
		second order wins — so the baseline belongs to the wrong order and every
		Variance to Plan after it is measured against the wrong number. One
		process cannot demonstrate two committing at once, so this asserts the
		mechanism that prevents it, which is the thing a later tidy-up would
		remove without noticing.
		"""
		scope = self._scope()
		locked = []
		real_get_value = frappe.db.get_value

		def watching(*args, **kwargs):
			if args[:2] == ("Scope Item", scope) and kwargs.get("for_update"):
				locked.append(args)
			return real_get_value(*args, **kwargs)

		frappe.db.get_value = watching
		try:
			self._order(scope, rate=4_000)
		finally:
			frappe.db.get_value = real_get_value

		self.assertTrue(locked, "the scope's plan was read without locking the row")

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
		if not frappe.db.exists("Measurement Rule", {"item_group": cls.group}):
			frappe.get_doc(
				{
					"doctype": "Measurement Rule",
					"rule_title": "Insite Journey Glass",
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

	def _measured_quotation(self):
		return frappe.get_doc(
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
		)

	def test_a_rule_change_after_a_quote_never_breaks_the_order(self):
		"""Freeze: a measured line keeps the quantity it was recorded with.

		A rule edited between quoting and ordering used to re-derive the ordered
		line — and when it derived zero, the save failed with "Quantity cannot be
		zero" and there was no way forward. The line now keeps what it was
		measured under; re-measuring it (as the desk does when a box changes)
		takes up the changed rule.
		"""
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		from insite.api import line_preview

		measured = 1.5 * 2.8 * 40  # 168
		quotation = self._measured_quotation().insert()
		self.assertAlmostEqual(quotation.items[0].qty, measured)
		quotation.submit()

		rule = frappe.get_doc("Measurement Rule", {"item_group": self.group})
		original = rule.formula
		try:
			rule.formula = "height * width * count * 2"  # the same rule, now doubled
			rule.save(ignore_permissions=True)

			order = make_sales_order(quotation.name)
			order.delivery_date = frappe.utils.add_days(frappe.utils.today(), 30)
			order.project = self.project
			order.insert()  # must not throw, and must not silently double the order
			self.assertAlmostEqual(
				order.items[0].qty, measured, msg="the ordered quote kept the quantity it was measured with"
			)

			# Re-measure the line the way the desk does: the box changes, the
			# client syncs qty from the preview, and the server then recomputes.
			order.items[0].custom_base_qty = 41
			order.items[0].qty = line_preview(
				self.item, {"custom_height": 1.5, "custom_width": 2.8, "custom_base_qty": 41}
			)["quantity"]
			order.save()
			self.assertAlmostEqual(order.items[0].qty, 1.5 * 2.8 * 41 * 2)
		finally:
			rule.formula = original
			rule.save(ignore_permissions=True)

	def test_a_return_records_the_measurement_without_flipping_the_quantity(self):
		"""A return keeps its negative quantity and still reads as measured.

		The engine never recalculates a return — a formula cannot produce the
		negative quantity that makes it a return — but it does stamp how the
		returned work was measured, so the credit note reads as measured instead
		of blank. Touching a measurement box on it must not flip the sign.
		"""
		from erpnext.controllers.sales_and_purchase_return import make_return_doc

		measured = 1.5 * 2.8 * 40  # 168
		delivery = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
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
		self.assertAlmostEqual(delivery.items[0].qty, measured)
		delivery.submit()

		credit = make_return_doc("Delivery Note", delivery.name)
		credit.insert()
		self.assertAlmostEqual(
			credit.items[0].qty, -measured, msg="a return keeps the negative quantity it was created with"
		)
		self.assertTrue(
			credit.items[0].custom_calc_source, "the return should still read as measured, not blank"
		)


class TestScopeProfitability(IntegrationTestCase):
	"""Money still to be spent is money already lost, and no ledger holds it.

	ERPNext reports what has been posted. A Purchase Order has not been posted,
	so a scope reads as profitable until the invoices arrive. These tests are
	about that gap.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.customer = _ensure(
			"Customer",
			{"customer_name": "Insite Margin Customer"},
			{"customer_name": "Insite Margin Customer", "customer_type": "Company"},
		)
		cls.supplier = _ensure(
			"Supplier",
			{"supplier_name": "Insite Margin Supplier"},
			{"supplier_name": "Insite Margin Supplier", "supplier_group": "All Supplier Groups"},
		)
		cls.item = _ensure(
			"Item",
			{"item_code": "INSITE-MARGIN-ITEM"},
			{
				"item_code": "INSITE-MARGIN-ITEM",
				"item_name": "Insite Margin Item",
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
			},
		)
		cls.project = _ensure(
			"Project",
			{"project_name": "Insite Margin Project"},
			{"project_name": "Insite Margin Project", "company": cls.company, "status": "Open"},
		)
		frappe.db.commit()

	def setUp(self):
		self.scope = (
			frappe.get_doc(
				{
					"doctype": "Scope Item",
					"scope_title": f"Margin {frappe.generate_hash(length=8)}",
					"project": self.project,
					"status": "Active",
				}
			)
			.insert()
			.name
		)

	def _sold(self, rate, qty=1):
		order = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 30),
				"items": [{"item_code": self.item, "qty": qty, "rate": rate, "scope_item": self.scope}],
			}
		)
		order.insert()
		order.submit()
		return order

	def _bought(self, rate, qty=1):
		order = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": self.supplier,
				"company": self.company,
				"project": self.project,
				"schedule_date": frappe.utils.add_days(frappe.utils.today(), 15),
				"items": [{"item_code": self.item, "qty": qty, "rate": rate, "scope_item": self.scope}],
			}
		)
		order.insert()
		order.submit()
		return order

	def _row(self):
		from insite.insite.report.scope_profitability.scope_profitability import execute

		_, rows = execute({"company": self.company, "project": self.project})
		return next(row for row in rows if row["scope"] == self.scope)

	def test_a_purchase_order_is_a_cost_before_it_is_an_invoice(self):
		self._sold(rate=10_000)
		self._bought(rate=6_000)

		row = self._row()
		self.assertAlmostEqual(row["contract_value"], 10_000)
		# Nothing is posted yet, so the ledger sees no cost at all.
		self.assertAlmostEqual(row["cost"], 0)
		self.assertAlmostEqual(row["committed"], 6_000)
		self.assertAlmostEqual(row["expected_cost"], 6_000)
		self.assertAlmostEqual(row["margin"], 4_000)
		self.assertAlmostEqual(row["margin_pct"], 40.0)

	def _billed(self, rate, qty=1):
		"""A real Purchase Invoice on the scope, with no link back to any order.

		Deliberately unlinked: `billed_amt` on the order never sees it, so the
		order stays committed. Under Insite's over-stating rule the spend then
		shows as both Cost and Committed — the safe error, documented on
		`scope_totals.committed_by_scope`.
		"""
		bill = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": self.supplier,
				"company": self.company,
				"project": self.project,
				"items": [{"item_code": self.item, "qty": qty, "rate": rate, "scope_item": self.scope}],
			}
		)
		bill.insert()
		bill.submit()
		return bill

	def test_invoicing_the_order_itself_stops_it_being_committed(self):
		"""billed_amt tracks an invoice raised from the order, so committed clears."""
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		self._sold(rate=10_000)
		order = self._bought(rate=6_000)
		self.assertAlmostEqual(self._row()["committed"], 6_000)

		bill = frappe.get_doc(make_purchase_invoice(order.name))
		bill.insert()
		bill.submit()
		self.assertAlmostEqual(self._row()["committed"], 0)

	def test_an_unlinked_invoice_leaves_the_order_committed(self):
		"""Over-stating is the safe error, and it never goes negative.

		An invoice keyed without a link back to its order — the everyday
		accounts-office case — leaves `billed_amt` at zero, so the order stays
		fully committed even when the invoice is larger than it. The spend then
		shows once as Cost and once as Committed until the order is linked or
		Closed. The alternative — netting invoices against orders — hid a live
		liability, so this is deliberate; see `scope_totals.committed_by_scope`.
		"""
		self._sold(rate=10_000)
		self._bought(rate=6_000)
		self._billed(7_000)  # unlinked, and larger than the order

		row = self._row()
		self.assertAlmostEqual(row["committed"], 6_000)  # unchanged, never negative
		self.assertAlmostEqual(row["cost"], 7_000, places=2)
		self.assertAlmostEqual(row["expected_cost"], 13_000, places=2)

	def test_a_closed_order_is_no_longer_money_we_are_going_to_spend(self):
		self._sold(rate=10_000)
		order = self._bought(rate=6_000)
		self.assertAlmostEqual(self._row()["committed"], 6_000)

		order.update_status("Closed")

		self.assertAlmostEqual(self._row()["committed"], 0)
		self.assertAlmostEqual(self._row()["margin"], 10_000)

	def test_the_worst_scope_is_the_first_row(self):
		from insite.insite.report.scope_profitability.scope_profitability import execute

		self._sold(rate=10_000)
		self._bought(rate=1_000)
		healthy = self.scope

		self.setUp()  # a second scope on the same project
		self._sold(rate=10_000)
		self._bought(rate=9_000)
		thin = self.scope

		_, rows = execute({"company": self.company, "project": self.project})
		ours = [row["scope"] for row in rows if row["scope"] in (healthy, thin)]
		self.assertEqual(ours, [thin, healthy])

	def test_the_scope_picker_offers_only_this_projects_scopes(self):
		"""The search behind the Scope field on a document line.

		Found in a browser, not here: the picker was offering every scope in the
		company across every project. The client was adding a `project` to the
		filters of ERPNext's dimension search, which reads `dimension`, `account`
		and `company` and ignores every other key — so the filter went nowhere,
		someone could pick a scope from another job, and the server then refused
		the document it had just invited them to build.
		"""
		from insite.api import scope_query

		mine = self.scope
		theirs = (
			frappe.get_doc(
				{
					"doctype": "Scope Item",
					"scope_title": f"Elsewhere {frappe.generate_hash(length=6)}",
					"project": _ensure(
						"Project",
						{"project_name": "Insite Other Margin Project"},
						{
							"project_name": "Insite Other Margin Project",
							"company": self.company,
							"status": "Open",
						},
					),
					"status": "Active",
				}
			)
			.insert()
			.name
		)

		def ask(project):
			rows = scope_query(
				"Scope Item",
				"",
				"name",
				0,
				100,
				{"dimension": "scope_item", "account": "", "company": self.company, "project": project},
			)
			return {row[0] for row in rows}

		offered = ask(frappe.db.get_value("Scope Item", mine, "project"))
		self.assertIn(mine, offered)
		self.assertNotIn(theirs, offered, "the picker offered a scope from another project")

		# and ERPNext's own filtering still applies underneath
		self.assertIn(theirs, ask(frappe.db.get_value("Scope Item", theirs, "project")))

	def test_the_scope_picker_needs_a_company_to_answer_at_all(self):
		"""ERPNext's dimension search filters on the company unconditionally.

		If nothing supplies one it filters on `company = None` and the picker
		comes back empty. That is the shape of the Quotation, where the Scope
		field is Insite's own and carries no ERPNext query to inherit a company
		from — so the client sends one, and this records why.
		"""
		from insite.api import scope_query

		project = frappe.db.get_value("Scope Item", self.scope, "project")
		base = {"dimension": "scope_item", "account": "", "project": project}

		with_company = scope_query("Scope Item", "", "name", 0, 100, {**base, "company": self.company})
		self.assertIn(self.scope, {row[0] for row in with_company})

		without = scope_query("Scope Item", "", "name", 0, 100, base)
		self.assertEqual(without, [], "a company-less search should return nothing, not everything")

	def test_a_quotation_offers_projects_of_its_party_only_when_it_is_a_customer(self):
		"""The Project picker on a Quotation.

		ERPNext narrows the project to the customer on the Sales Order, Delivery
		Note and Sales Invoice, and there is nothing to rebuild there. But it
		reads `doc.customer`, and a Quotation has no such field — its party is
		`party_name`, and only a customer when `quotation_to` says so. So on a
		Quotation nothing narrowed. This checks the query the client now sends.
		"""
		from erpnext.controllers.queries import get_project_name

		mine = _ensure(
			"Project",
			{"project_name": "Insite Party Project"},
			{
				"project_name": "Insite Party Project",
				"company": self.company,
				"status": "Open",
				"customer": self.customer,
			},
		)
		other_customer = _ensure(
			"Customer",
			{"customer_name": "Insite Other Party"},
			{"customer_name": "Insite Other Party", "customer_type": "Company"},
		)
		theirs = _ensure(
			"Project",
			{"project_name": "Insite Other Party Project"},
			{
				"project_name": "Insite Other Party Project",
				"company": self.company,
				"status": "Open",
				"customer": other_customer,
			},
		)

		def ask(customer):
			rows = get_project_name(
				"Project", "", "name", 0, 100, {"customer": customer, "company": self.company}
			)
			return {row[0] for row in rows}

		offered = ask(self.customer)
		self.assertIn(mine, offered)
		self.assertNotIn(theirs, offered, "the picker offered another customer's project")

		# A project nobody has assigned is still offered: ERPNext does not make
		# the field mandatory, and a site that leaves it blank must not end up
		# with an empty picker on every document.
		unassigned = _ensure(
			"Project",
			{"project_name": "Insite Unassigned Project"},
			{"project_name": "Insite Unassigned Project", "company": self.company, "status": "Open"},
		)
		self.assertIn(unassigned, ask(self.customer))

		# And with no customer at all — a Quotation to a Lead — nothing narrows.
		self.assertIn(theirs, ask(None))

	def test_collecting_a_payment_can_be_narrowed_to_one_job(self):
		"""The outstanding invoices offered when a payment comes in.

		A contractor is paid per project, and allocating a receipt against
		another job's invoice is how money ends up on the wrong contract.
		ERPNext's search filters by any active accounting dimension — so the
		Scope already worked — but it builds those conditions from a dimension
		list that leaves Project out, so a project handed to it was dropped.
		"""
		from insite.overrides.payment_entry import get_outstanding_reference_documents

		other_project = _ensure(
			"Project",
			{"project_name": "Insite Second Job"},
			{"project_name": "Insite Second Job", "company": self.company, "status": "Open"},
		)

		def invoice(project, amount):
			doc = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": self.customer,
					"company": self.company,
					"project": project,
					"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
					"items": [{"item_code": self.item, "qty": 1, "rate": amount}],
				}
			)
			doc.insert()
			doc.submit()
			return doc.name

		this_job = invoice(self.project, 4_000)
		other_job = invoice(other_project, 9_000)

		receivable = frappe.get_cached_value("Company", self.company, "default_receivable_account")
		args = {
			"posting_date": frappe.utils.today(),
			"company": self.company,
			"party_type": "Customer",
			"party": self.customer,
			"payment_type": "Receive",
			"party_account": receivable,
			"get_outstanding_invoices": True,
		}

		everything = {row.get("voucher_no") for row in get_outstanding_reference_documents(dict(args))}
		self.assertIn(this_job, everything)
		self.assertIn(other_job, everything, "both invoices are outstanding to begin with")

		narrowed = {
			row.get("voucher_no")
			for row in get_outstanding_reference_documents({**args, "project": self.project})
		}
		self.assertIn(this_job, narrowed)
		self.assertNotIn(other_job, narrowed, "another job's invoice was offered for this payment")

	def test_collecting_a_payment_can_be_narrowed_to_one_scope(self):
		"""The Scope filter in that same dialog.

		It is there because Insite registers the Scope as an accounting
		dimension, and it always came back empty: ERPNext filters the payment
		ledger, and the ledger row behind an invoice is the receivable posting,
		which carries the header's dimensions and no scope at all — a scope
		belongs to a line. So the dialog reported that a customer owed nothing
		on a scope they owe plenty on. A scope is matched on the lines instead.
		"""
		from insite.overrides.payment_entry import get_outstanding_reference_documents

		def invoice(scope, amount):
			doc = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": self.customer,
					"company": self.company,
					"project": self.project,
					"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
					"items": [{"item_code": self.item, "qty": 1, "rate": amount, "scope_item": scope}],
				}
			)
			doc.insert()
			doc.submit()
			return doc.name

		this_scope = self.scope
		self.setUp()  # a second scope on the same project
		other_scope = self.scope

		mine = invoice(this_scope, 3_000)
		theirs = invoice(other_scope, 8_000)

		args = {
			"posting_date": frappe.utils.today(),
			"company": self.company,
			"party_type": "Customer",
			"party": self.customer,
			"payment_type": "Receive",
			"party_account": frappe.get_cached_value("Company", self.company, "default_receivable_account"),
			"get_outstanding_invoices": True,
		}

		everything = {row.get("voucher_no") for row in get_outstanding_reference_documents(dict(args))}
		self.assertTrue({mine, theirs} <= everything, "both invoices are outstanding to begin with")

		narrowed = {
			row.get("voucher_no")
			for row in get_outstanding_reference_documents({**args, "scope_item": this_scope})
		}
		self.assertIn(
			mine,
			narrowed,
			"the scope filter found nothing, which is what it did before: ERPNext "
			"filtered the payment ledger on a scope that is never set there",
		)
		self.assertNotIn(theirs, narrowed)

	def test_the_reports_insite_does_not_build_are_really_there(self):
		"""The workspace points at these instead of Insite rebuilding them.

		Both work per scope because Insite registers the Scope as an accounting
		dimension. If ERPNext ever renames one, the workspace grows a dead tile
		and the offline guard cannot see it.
		"""
		from insite.tests.test_app_structure import BORROWED_REPORTS

		for report in BORROWED_REPORTS:
			self.assertTrue(frappe.db.exists("Report", report), f"ERPNext no longer ships {report}")

	def test_the_scope_is_an_accounting_dimension_the_ledger_keeps(self):
		"""Everything above rests on the scope reaching the GL."""
		self.assertTrue(frappe.db.has_column("GL Entry", "scope_item"))
		self.assertTrue(
			frappe.db.exists("Accounting Dimension", {"document_type": "Scope Item", "disabled": 0})
		)


class TestFilteringReportsByCustomer(IntegrationTestCase):
	"""A contractor works for several clients at once.

	"Show me everything for this customer" is the question the reports could not
	answer — they took a project and nothing above it. A customer is not on a
	Scope Item, it is on the Project, so all three narrow the same way through
	one helper. Two reports disagreeing about who a customer is would be worse
	than neither of them knowing.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.ours = _ensure(
			"Customer",
			{"customer_name": "Insite Filter Ours"},
			{"customer_name": "Insite Filter Ours", "customer_type": "Company"},
		)
		cls.theirs = _ensure(
			"Customer",
			{"customer_name": "Insite Filter Theirs"},
			{"customer_name": "Insite Filter Theirs", "customer_type": "Company"},
		)
		cls.item = _ensure(
			"Item",
			{"item_code": "INSITE-FILTER-ITEM"},
			{
				"item_code": "INSITE-FILTER-ITEM",
				"item_name": "Insite Filter Item",
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
			},
		)
		cls.our_project = _ensure(
			"Project",
			{"project_name": "Insite Filter Ours Job"},
			{
				"project_name": "Insite Filter Ours Job",
				"company": cls.company,
				"status": "Open",
				"customer": cls.ours,
			},
		)
		cls.their_project = _ensure(
			"Project",
			{"project_name": "Insite Filter Theirs Job"},
			{
				"project_name": "Insite Filter Theirs Job",
				"company": cls.company,
				"status": "Open",
				"customer": cls.theirs,
			},
		)
		frappe.db.commit()

	def setUp(self):
		self.our_scope = self._scope(self.our_project, "Ours")
		self.their_scope = self._scope(self.their_project, "Theirs")

	def _scope(self, project, tag):
		return (
			frappe.get_doc(
				{
					"doctype": "Scope Item",
					"scope_title": f"Filter {tag} {frappe.generate_hash(length=6)}",
					"project": project,
					"status": "Active",
				}
			)
			.insert()
			.name
		)

	def _scopes_in(self, report_module, **filters):
		rows = report_module.execute({"company": self.company, **filters})[1]
		return {row.get("scope") for row in rows}

	def test_every_report_narrows_to_one_customer(self):
		from insite.insite.report.contract_progress import contract_progress
		from insite.insite.report.scope_profitability import scope_profitability

		for report in (contract_progress, scope_profitability):
			everything = self._scopes_in(report)
			self.assertTrue(
				{self.our_scope, self.their_scope} <= everything,
				f"{report.__name__}: both scopes should show with no customer filter",
			)

			ours = self._scopes_in(report, customer=self.ours)
			self.assertIn(self.our_scope, ours, report.__name__)
			self.assertNotIn(self.their_scope, ours, f"{report.__name__} showed another customer's scope")

	def test_a_customer_and_a_project_that_is_not_theirs_gives_nothing(self):
		from insite.insite.report.scope_profitability import scope_profitability

		mixed = self._scopes_in(scope_profitability, customer=self.ours, project=self.their_project)
		self.assertEqual(mixed, set(), "a customer and someone else's project should agree on nothing")

		matching = self._scopes_in(scope_profitability, customer=self.ours, project=self.our_project)
		self.assertIn(self.our_scope, matching)

	def test_a_customer_with_no_projects_narrows_to_nothing(self):
		"""Not to everything, which is the bug this shape of filter usually has."""
		from insite.insite.report.scope_profitability import scope_profitability

		stranger = _ensure(
			"Customer",
			{"customer_name": "Insite Filter Stranger"},
			{"customer_name": "Insite Filter Stranger", "customer_type": "Company"},
		)
		self.assertEqual(self._scopes_in(scope_profitability, customer=stranger), set())

	def test_the_register_narrows_to_the_same_customer(self):
		from insite.insite.report.measurement_register import measurement_register

		def invoice(project, scope, amount):
			doc = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": frappe.db.get_value("Project", project, "customer"),
					"company": self.company,
					"project": project,
					"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
					"items": [{"item_code": self.item, "qty": 1, "rate": amount, "scope_item": scope}],
				}
			)
			doc.insert()
			doc.submit()
			return doc.name

		mine = invoice(self.our_project, self.our_scope, 1_000)
		theirs = invoice(self.their_project, self.their_scope, 2_000)

		def documents(**filters):
			rows = measurement_register.execute({"company": self.company, **filters})[1]
			return {row["document"] for row in rows}

		self.assertTrue({mine, theirs} <= documents())
		narrowed = documents(customer=self.ours)
		self.assertIn(mine, narrowed)
		self.assertNotIn(theirs, narrowed)


class TestTheIntegrityFixes(IntegrationTestCase):
	"""The things two reviewers found by attacking the app on a bench.

	Every one of these passed the suite before it was found, so each test here
	is the shape of a bug that shipped.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _a_company()
		cls.customer = _ensure(
			"Customer",
			{"customer_name": "Integrity Customer"},
			{"customer_name": "Integrity Customer", "customer_type": "Company"},
		)
		cls.supplier = _ensure(
			"Supplier",
			{"supplier_name": "Integrity Supplier"},
			{"supplier_name": "Integrity Supplier", "supplier_group": "All Supplier Groups"},
		)
		cls.item = _ensure(
			"Item",
			{"item_code": "INTEGRITY-ITEM"},
			{
				"item_code": "INTEGRITY-ITEM",
				"item_name": "Integrity Item",
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
			},
		)
		cls.project = _ensure(
			"Project",
			{"project_name": "Integrity Project"},
			{"project_name": "Integrity Project", "company": cls.company, "status": "Open"},
		)
		cls.other_project = _ensure(
			"Project",
			{"project_name": "Integrity Other Project"},
			{"project_name": "Integrity Other Project", "company": cls.company, "status": "Open"},
		)
		frappe.db.commit()

	def setUp(self):
		self.scope = self._scope(self.project)

	def _scope(self, project):
		return (
			frappe.get_doc(
				{
					"doctype": "Scope Item",
					"scope_title": f"Integrity {frappe.generate_hash(length=6)}",
					"project": project,
					"status": "Active",
				}
			)
			.insert()
			.name
		)

	def _order(self, rate, doctype="Sales Order", scope=None, **extra):
		values = {
			"doctype": doctype,
			"company": self.company,
			"project": self.project,
			"items": [{"item_code": self.item, "qty": 1, "rate": rate, "scope_item": scope or self.scope}],
			**extra,
		}
		if doctype == "Sales Order":
			values["customer"] = self.customer
			values["delivery_date"] = frappe.utils.add_days(frappe.utils.today(), 30)
		else:
			values["supplier"] = self.supplier
			values["schedule_date"] = frappe.utils.add_days(frappe.utils.today(), 15)
		doc = frappe.get_doc(values)
		doc.insert()
		doc.submit()
		return doc

	# --- the money columns are net, like the ledger --------------------------

	def test_a_discount_moves_invoiced_and_revenue_together(self):
		from insite.insite.report.contract_progress import contract_progress
		from insite.insite.report.scope_profitability import scope_profitability

		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": self.customer,
				"company": self.company,
				"project": self.project,
				"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
				"items": [{"item_code": self.item, "qty": 1, "rate": 100_000, "scope_item": self.scope}],
				"apply_discount_on": "Grand Total",
				"discount_amount": 10_000,
			}
		)
		invoice.insert()
		invoice.submit()

		def row_of(module):
			rows = module.execute({"company": self.company})[1]
			return next(r for r in rows if r["scope"] == self.scope)

		invoiced = row_of(contract_progress)["invoiced"]
		revenue = row_of(scope_profitability)["revenue"]
		self.assertAlmostEqual(invoiced, 90_000, places=2)
		self.assertAlmostEqual(revenue, 90_000, places=2)
		self.assertAlmostEqual(invoiced, revenue, places=2, msg="the two reports disagree")

	def test_the_plan_is_the_price_that_was_agreed(self):
		self._order(100_000, apply_discount_on="Grand Total", discount_amount=25_000)
		self.assertAlmostEqual(
			flt(frappe.db.get_value("Scope Item", self.scope, "planned_amount")), 75_000, places=2
		)

	# --- committed cost errs by over-stating, never by hiding a liability ----

	def test_an_order_invoiced_from_itself_stops_being_committed(self):
		"""billed_amt tracks an invoice raised from the order, so committed clears."""
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		from insite.scope_totals import committed_by_scope

		po = self._order(10_000, doctype="Purchase Order")
		self.assertAlmostEqual(committed_by_scope([self.scope], self.company)[self.scope], 10_000)

		bill = frappe.get_doc(make_purchase_invoice(po.name))
		bill.insert()
		bill.submit()

		committed = committed_by_scope([self.scope], self.company).get(self.scope, 0)
		self.assertAlmostEqual(
			committed, 0, places=2, msg="invoiced from the order itself; nothing is still committed"
		)

	def test_an_unlinked_invoice_never_eats_a_different_orders_commitment(self):
		"""Regression: netting invoices against orders under-stated what was owed.

		A 260,000 order at 0% billed once read as 211,650 committed, because an
		off-order invoice on the same scope was subtracted straight out of it. An
		open order is money still owed. An invoice keyed without ``po_detail``
		leaves ``billed_amt`` at zero, so the order stays fully committed — the
		safe error. The residual double-count with Cost is documented in
		``scope_totals.committed_by_scope``.
		"""
		from insite.scope_totals import committed_by_scope

		self._order(260_000, doctype="Purchase Order")  # 0% billed, fully open

		bill = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": self.supplier,
				"company": self.company,
				"project": self.project,
				"items": [{"item_code": self.item, "qty": 1, "rate": 48_350, "scope_item": self.scope}],
			}
		)
		bill.insert()
		bill.submit()

		committed = committed_by_scope([self.scope], self.company)[self.scope]
		self.assertAlmostEqual(
			committed,
			260_000,
			places=2,
			msg="an unlinked invoice must not reduce a still-open order's commitment",
		)

	# --- a scope cannot wander onto another project's document ---------------

	def test_an_ordinary_line_cannot_carry_another_projects_scope(self):
		"""The old check looked only at lines a rule had matched."""
		theirs = self._scope(self.other_project)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": self.customer,
					"company": self.company,
					"project": self.project,
					"due_date": frappe.utils.add_days(frappe.utils.today(), 30),
					"items": [{"item_code": self.item, "qty": 1, "rate": 1000, "scope_item": theirs}],
				}
			).insert()

	def test_a_purchase_document_cannot_either(self):
		"""Nothing checked the buying side at all."""
		theirs = self._scope(self.other_project)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Purchase Order",
					"supplier": self.supplier,
					"company": self.company,
					"project": self.project,
					"schedule_date": frappe.utils.add_days(frappe.utils.today(), 15),
					"items": [{"item_code": self.item, "qty": 1, "rate": 1000, "scope_item": theirs}],
				}
			).insert()

	# --- a cancelled order is not a plan -------------------------------------

	def test_cancelling_the_only_order_forgets_the_plan(self):
		order = self._order(50_000)
		self.assertAlmostEqual(flt(frappe.db.get_value("Scope Item", self.scope, "planned_amount")), 50_000)

		order.cancel()
		self.assertFalse(
			flt(frappe.db.get_value("Scope Item", self.scope, "planned_amount")),
			"the plan outlived the order that set it",
		)

	def test_cancelling_one_of_two_orders_keeps_the_plan(self):
		first = self._order(50_000)
		self._order(20_000)  # a variation
		first.cancel()

		self.assertAlmostEqual(
			flt(frappe.db.get_value("Scope Item", self.scope, "planned_amount")),
			50_000,
			msg="another order still stands, so the baseline should hold",
		)

	# --- closed orders are not live work -------------------------------------

	def test_a_closed_sales_order_stops_counting_as_ordered(self):
		from insite.insite.report.contract_progress import contract_progress

		order = self._order(60_000)

		def ordered():
			rows = contract_progress.execute({"company": self.company})[1]
			return next(r for r in rows if r["scope"] == self.scope)["ordered"]

		self.assertAlmostEqual(ordered(), 60_000, places=2)
		order.update_status("Closed")
		self.assertAlmostEqual(ordered(), 0, places=2)

	# --- negative measurements -----------------------------------------------

	def test_two_negative_measurements_do_not_multiply_into_a_quantity(self):
		"""Minus two by minus one and a half is a plausible-looking three."""
		measured = _a_measured_item()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Sales Order",
					"customer": self.customer,
					"company": self.company,
					"project": self.project,
					"delivery_date": frappe.utils.add_days(frappe.utils.today(), 30),
					"items": [
						{
							"item_code": measured,
							"qty": 1,
							"rate": 100,
							"scope_item": self.scope,
							"custom_height": -2,
							"custom_width": -1.5,
							"custom_base_qty": 4,
						}
					],
				}
			).insert()


def _a_measured_item():
	"""An item a rule matches, with a rule to match it."""
	group = "Integrity Measured Group"
	if not frappe.db.exists("Item Group", group):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": group, "parent_item_group": "All Item Groups"}
		).insert(ignore_permissions=True)

	code = "INTEGRITY-MEASURED"
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": "Integrity Measured",
				"item_group": group,
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Measurement Rule", {"item_group": group}):
		frappe.get_doc(
			{
				"doctype": "Measurement Rule",
				"rule_title": "Integrity Area",
				"apply_on": "Item Group",
				"item_group": group,
				"preset": "Area",
				"inputs": [
					{"source": "Line", "field_name": "custom_height", "token": "height"},
					{"source": "Line", "field_name": "custom_width", "token": "width"},
					{"source": "Line", "field_name": "custom_base_qty", "token": "count"},
				],
				"formula": "height * width * count",
			}
		).insert(ignore_permissions=True)
	return code


class TestReportTotals(IntegrationTestCase):
	"""The totals line is worked out from the totals, never by averaging.

	Frappe's own total row averaged the Percent columns: 42.84%, 0, 0 came out
	as 14.28%, and 294,000 of 744,632 read as anything but the 39.5% it is. The
	reports now turn that off and total their own money, then divide once. These
	exercise the pure total-row helpers, so they are deterministic.
	"""

	def test_contract_progress_percent_is_from_the_totals(self):
		from insite.insite.report.contract_progress.contract_progress import _total_row

		rows = [
			{
				"planned": 0,
				"ordered": 700_000,
				"variance_to_plan": 0,
				"delivered": 0,
				"rejected_open": 0,
				"invoiced": 294_000,
				"variance": 406_000,  # committed 700,000 − invoiced 294,000
			},
			{
				"planned": 0,
				"ordered": 44_632,
				"variance_to_plan": 0,
				"delivered": 0,
				"rejected_open": 0,
				"invoiced": 0,
				"variance": 44_632,
			},
		]
		total = _total_row(rows)
		# 294,000 invoiced of 744,632 committed is 39.48%, not the 14.28% you get
		# by averaging 42.0%, 0 and 0.
		self.assertAlmostEqual(total["pct_invoiced"], 294_000 / 744_632 * 100.0, places=2)
		self.assertAlmostEqual(total["invoiced"], 294_000)

	def test_scope_profitability_margin_percent_is_from_the_totals(self):
		from insite.insite.report.scope_profitability.scope_profitability import _total_row

		rows = [
			{
				"contract_value": 30_000,
				"revenue": 0,
				"cost": 0,
				"committed": 0,
				"expected_cost": 0,
				"margin": 30_000,
				"margin_pct": 100.0,
			},
			{
				"contract_value": 10_000,
				"revenue": 0,
				"cost": 10_000,
				"committed": 0,
				"expected_cost": 10_000,
				"margin": 0,
				"margin_pct": 0.0,
			},
		]
		total = _total_row(rows)
		# 30,000 margin on 40,000 of contract value is 75%, not the 50% you get by
		# averaging 100% and 0%.
		self.assertAlmostEqual(total["margin_pct"], 75.0)
		self.assertAlmostEqual(total["margin"], 30_000)
