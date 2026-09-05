"""Integration tests for the Measurement Field master — run on a bench.

bench --site <site> run-tests --app insite
"""

import frappe
from frappe.tests import IntegrationTestCase


class TestTheShippedMeasurementFields(IntegrationTestCase):
	"""The five boxes Insite ships are records in the master, and they stay.

	They are in the list for the same reason UOM ships Nos and Kg: one place
	that shows every measurable number. They cannot be deleted for a harder
	reason — deleting a Measurement Field deletes its Custom Field, and deleting
	a Custom Field drops the column with every measurement in it.
	"""

	def test_install_records_all_five(self):
		from insite.insite.doctype.measurement_field.measurement_field import STANDARD_FIELDS

		for field_name, label, _help in STANDARD_FIELDS:
			name = frappe.db.get_value("Measurement Field", {"field_name": field_name}, "name")
			self.assertTrue(name, f"{label} is not in the master")
			self.assertTrue(frappe.db.get_value("Measurement Field", name, "is_standard"))

	def test_recording_them_is_idempotent(self):
		from insite.insite.doctype.measurement_field.measurement_field import (
			STANDARD_FIELDS,
			ensure_standard_fields,
		)

		before = frappe.db.count("Measurement Field")
		ensure_standard_fields()
		ensure_standard_fields()
		self.assertEqual(frappe.db.count("Measurement Field"), before)
		self.assertEqual(frappe.db.count("Measurement Field", {"is_standard": 1}), len(STANDARD_FIELDS))

	def test_a_shipped_field_cannot_be_deleted(self):
		name = frappe.db.get_value("Measurement Field", {"field_name": "custom_height"}, "name")
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Measurement Field", name, ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Measurement Field", name))
		self.assertTrue(frappe.db.has_column("Sales Order Item", "custom_height"))

	def test_a_shipped_field_keeps_its_place_on_the_line(self):
		"""Applying it from the record would move it to the end of the section."""
		field = frappe.get_doc("Measurement Field", {"field_name": "custom_height"})
		before = frappe.db.get_value(
			"Custom Field", {"dt": "Sales Order Item", "fieldname": "custom_height"}, "insert_after"
		)
		field.apply()
		after = frappe.db.get_value(
			"Custom Field", {"dt": "Sales Order Item", "fieldname": "custom_height"}, "insert_after"
		)
		self.assertEqual(before, after)

	def test_a_field_holding_measurements_cannot_be_deleted(self):
		"""The real hole: nothing measured BY it, but documents measured INTO it."""
		field = frappe.get_doc(
			{
				"doctype": "Measurement Field",
				"field_label": f"Panes {frappe.generate_hash(length=5)}",
				"applies_to": "Transaction line",
			}
		).insert(ignore_permissions=True)

		# nothing uses it and nothing holds a value: it may go
		self.assertFalse(frappe.get_all("Measurement Input", filters={"field_name": field.field_name}))

		order = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": _a_customer(),
				"company": _a_company(),
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 30),
				"items": [
					{"item_code": _an_item(), "qty": 1, "rate": 100, field.field_name: 4},
				],
			}
		)
		order.insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Measurement Field", field.name, ignore_permissions=True)
		self.assertTrue(
			frappe.db.has_column("Sales Order Item", field.field_name),
			"the column was dropped with the measurements in it",
		)

		# once nothing holds a value, it may go
		order.delete()
		frappe.delete_doc("Measurement Field", field.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Measurement Field", field.name))


class TestSiteFieldsStayInTheMeasurementSection(IntegrationTestCase):
	"""A site field must land in the Measurements section, never past it.

	Every site field, and the Calculated section break, was inserted after
	Wastage. When both claimed that one slot the second site field resolved
	*after* the break — inside the collapsed Calculated section, where its box
	could not be typed into. Silent, and it killed the app's headline feature.
	"""

	def test_two_site_fields_chain_before_the_calculated_break(self):
		from insite.insite.doctype.measurement_field.measurement_field import CALC_SECTION_BREAK

		suffix = frappe.generate_hash(length=5)
		one = frappe.get_doc(
			{
				"doctype": "Measurement Field",
				"field_label": f"Panels A {suffix}",
				"applies_to": "Transaction line",
			}
		).insert(ignore_permissions=True)
		two = frappe.get_doc(
			{
				"doctype": "Measurement Field",
				"field_label": f"Panels B {suffix}",
				"applies_to": "Transaction line",
			}
		).insert(ignore_permissions=True)

		def anchor(fieldname, doctype="Sales Order Item"):
			return frappe.db.get_value(
				"Custom Field", {"dt": doctype, "fieldname": fieldname}, "insert_after"
			)

		try:
			# The two newest site fields chain in creation order, and the
			# Calculated section break sits after the last of them — never before.
			self.assertEqual(anchor(two.field_name), one.field_name)
			self.assertEqual(
				anchor(CALC_SECTION_BREAK),
				two.field_name,
				"the second field slipped past the Calculated section break",
			)
			# Neither field is anchored after the break — that was the bug.
			self.assertNotEqual(anchor(one.field_name), CALC_SECTION_BREAK)
			self.assertNotEqual(anchor(two.field_name), CALC_SECTION_BREAK)

			# Removing the last one closes the gap: the break falls back onto it.
			frappe.delete_doc("Measurement Field", two.name, ignore_permissions=True)
			self.assertEqual(anchor(CALC_SECTION_BREAK), one.field_name)
		finally:
			for name in (two.name, one.name):
				if frappe.db.exists("Measurement Field", name):
					frappe.delete_doc("Measurement Field", name, ignore_permissions=True)


def _a_company():
	return frappe.get_all("Company", pluck="name")[0]


def _a_customer():
	existing = frappe.get_all("Customer", pluck="name")
	if existing:
		return existing[0]
	return (
		frappe.get_doc({"doctype": "Customer", "customer_name": "MF Test", "customer_type": "Company"})
		.insert(ignore_permissions=True)
		.name
	)


def _an_item():
	code = "INSITE-MF-ITEM"
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": "Insite MF Item",
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
	return code
