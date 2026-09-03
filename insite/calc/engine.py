"""Frappe glue around the pure calc core: load rules, resolve, apply to rows."""
from __future__ import annotations
import json
import frappe
from frappe.utils import cint, flt
from insite.calc import measures
from insite.calc.resolve import resolve_rule

_TARGET_FIELD = "qty"
_PRECISION = 3


def has_rules():
    return bool(frappe.get_all("Work Item Type", filters={"disabled": 0}, limit=1))


def load_rules():
    rules = []
    types = frappe.get_all("Work Item Type", filters={"disabled": 0}, fields=["name", "modified"],
                           order_by="modified desc")
    for t in types:
        doc = frappe.get_cached_doc("Work Item Type", t.name)
        for row in doc.measurement_rules:
            rules.append({
                "source": doc.name, "measure": row.measure, "formula": row.formula,
                "apply_on": row.apply_on, "item_code": row.item_code,
                "item_template": row.item_template, "item_group": row.item_group,
                "item_attribute": row.item_attribute, "attribute_value": row.attribute_value,
                "priority": cint(row.priority),
            })
    rules.sort(key=lambda r: r["priority"], reverse=True)  # stable; types already modified-desc
    return rules


def _item_meta(item_code):
    if not item_code:
        return None
    v = frappe.get_cached_value("Item", item_code,
                                ["item_group", "variant_of", "has_variants"], as_dict=True)
    return dict(v) if v else None


def _make_attr_getter():
    cache = {}
    def getter(item_code):
        if item_code not in cache:
            rows = frappe.get_all("Item Variant Attribute", filters={"parent": item_code},
                                  fields=["attribute", "attribute_value"])
            cache[item_code] = {r.attribute: r.attribute_value for r in rows}
        return cache[item_code]
    return getter


def _tokens(row):
    return {
        "height": flt(row.get("custom_height")),
        "width": flt(row.get("custom_width")),
        "length": flt(row.get("custom_length")),
        "count": flt(row.get("custom_base_qty")),
        "wastage": flt(row.get("custom_waste_factor")),
    }


def compute_qty_for_row(row, rule):
    tok = _tokens(row)
    qty = measures.compute(rule["measure"], formula=rule.get("formula"), **tok)
    return qty, tok


def apply_rule_to_row(row, rule):
    qty, tok = compute_qty_for_row(row, rule)
    row.set("custom_calc_measure", rule["measure"])
    row.set("custom_calc_source", rule["source"])
    row.set("custom_calc_dimensions", json.dumps(tok))
    if qty is None:  # manual
        return
    qty = flt(qty, _PRECISION)
    row.set(_TARGET_FIELD, qty)
    row.set("custom_calculated_qty", qty)


def recalculate_document(doc):
    items = doc.get("items")
    if not items or not has_rules():
        return 0
    rules = load_rules()
    if not rules:
        return 0
    attr_getter = _make_attr_getter()
    affected = 0
    for row in items:
        if not row.get("item_code"):
            continue
        meta = _item_meta(row.item_code)
        if not meta:
            continue
        item = {"item_code": row.item_code, "item_group": meta.get("item_group"),
                "variant_of": meta.get("variant_of"), "has_variants": meta.get("has_variants"),
                "attributes": attr_getter(row.item_code)}
        rule = resolve_rule(item, rules)
        if rule:
            apply_rule_to_row(row, rule)
            affected += 1
    return affected
