import frappe
from insite.calc.measures import compute


@frappe.whitelist()
def test_measure(measure, height=0, width=0, length=0, count=1, wastage=1, formula=None):
    frappe.only_for(["Contracting Manager", "System Manager"])
    qty = compute(measure, height=height, width=width, length=length,
                  count=count, wastage=wastage, formula=formula)
    return qty
