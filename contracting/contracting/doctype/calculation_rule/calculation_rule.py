import frappe
from frappe import _
from frappe.model.document import Document

FORMULA_AUTHOR_ROLES = {"Contracting Implementer", "System Manager", "Administrator"}


class CalculationRule(Document):
	def validate(self):
		self._validate_method()
		self._validate_scope()
		self._validate_formula_privilege()
		if not self.target_field:
			self.target_field = "qty"

	def _validate_method(self):
		if not self.calculation_method:
			return
		method = frappe.get_cached_value(
			"Calculation Method",
			self.calculation_method,
			["enabled", "is_formula"],
			as_dict=True,
		)
		if not method:
			frappe.throw(_("Calculation Method {0} does not exist.").format(self.calculation_method))
		if not method.enabled:
			frappe.throw(_("Calculation Method {0} is disabled.").format(self.calculation_method))
		self._method_is_formula = bool(method.is_formula)

	def _validate_scope(self):
		required = {
			"Item Code": "item_code",
			"Item Template": "item_template",
			"Item Attribute Value": "item_attribute",
			"Item Group": "item_group",
		}.get(self.apply_on)
		if required and not self.get(required):
			frappe.throw(
				_("{0} is required when Apply On is {1}.").format(
					_(self.meta.get_label(required)), self.apply_on
				)
			)
		if self.apply_on == "Item Attribute Value" and not self.attribute_value:
			frappe.throw(_("Attribute Value is required when Apply On is Item Attribute Value."))

	def _validate_formula_privilege(self):
		is_formula = getattr(self, "_method_is_formula", False) or self.calculation_method == "formula"
		if not is_formula:
			return
		if not (self.formula or "").strip():
			frappe.throw(_("A formula expression is required for the formula method."))
		user_roles = set(frappe.get_roles(frappe.session.user))
		if not (user_roles & FORMULA_AUTHOR_ROLES):
			frappe.throw(
				_("Only a Contracting Implementer may author or edit formula-based rules."),
				title=_("Not Permitted"),
			)
