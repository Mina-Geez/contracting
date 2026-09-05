"""Integration tests for the Measurement Rule — run on a bench, not with pytest.

	bench --site <site> run-tests --app insite

`in_plain_words` lives in this doctype's controller, so its tests live beside
it rather than three folders away.
"""

import frappe
from frappe.tests import IntegrationTestCase


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


class TestAddingAFieldWhileWritingARule(IntegrationTestCase):
	"""The Inputs grid offers "Add a new field…" as the last of its choices.

	Whoever is writing a rule needs a number Insite does not ship, and used to
	have to abandon a half-written rule, open Measurement Field, create it and
	find their place again. The dialog does it in the grid instead.

	That only works because a Measurement Field puts its column on the
	documents the moment it is saved. If it ever became deferred work, the rule
	would offer a field the line does not have, and the rule would save and then
	fail on a real document. These tests are that guarantee.
	"""

	def tearDown(self):
		for name in frappe.get_all(
			"Measurement Field", filters={"field_label": ["like", "Inline %"]}, pluck="name"
		):
			frappe.delete_doc("Measurement Field", name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def _add(self, label, applies_to="Transaction line"):
		return frappe.get_doc(
			{"doctype": "Measurement Field", "field_label": label, "applies_to": applies_to}
		).insert(ignore_permissions=True)

	def test_a_new_line_field_can_be_used_the_moment_it_is_made(self):
		from insite.insite.doctype.measurement_rule.measurement_rule import get_measurable_fields

		label = f"Inline Panels {frappe.generate_hash(length=5)}"
		field = self._add(label)

		offered = {row["value"]: row["label"] for row in get_measurable_fields("Line")}
		self.assertIn(field.field_name, offered, "the new field is not in the list the grid reads")
		self.assertEqual(offered[field.field_name], label)
		self.assertTrue(
			frappe.db.has_column("Sales Order Item", field.field_name),
			"the column is not on the line yet, so a rule using it would fail on a real document",
		)

	def test_a_new_item_field_lands_on_the_item_not_the_line(self):
		from insite.insite.doctype.measurement_rule.measurement_rule import get_measurable_fields

		label = f"Inline Sheet {frappe.generate_hash(length=5)}"
		field = self._add(label, applies_to="Item")

		self.assertIn(field.field_name, {row["value"] for row in get_measurable_fields("Item")})
		self.assertNotIn(field.field_name, {row["value"] for row in get_measurable_fields("Line")})
		self.assertTrue(frappe.db.has_column("Item", field.field_name))

	def test_the_name_the_dialog_never_asks_for_is_worked_out(self):
		"""The dialog asks for a label only. The fieldname is Insite's business."""
		field = self._add(f"Inline Number Of Panels {frappe.generate_hash(length=5)}")
		self.assertTrue(field.field_name.startswith("custom_"))
		self.assertNotIn(" ", field.field_name)
