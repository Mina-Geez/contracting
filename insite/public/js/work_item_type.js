frappe.ui.form.on("Work Item Type", {
  refresh(frm) {
    frm.add_custom_button(__("Test a Measure"), () => test_measure_dialog());
  },
});

function test_measure_dialog() {
  const d = new frappe.ui.Dialog({
    title: __("Test a Measure"),
    fields: [
      {fieldname: "measure", label: __("Measured By"), fieldtype: "Select",
       options: "area\nperimeter\nlinear\ncount\npiece_waste\nformula", default: "area"},
      {fieldname: "formula", label: __("Formula (plain words)"), fieldtype: "Data",
       depends_on: "eval:doc.measure=='formula'",
       description: __("Words: height, width, length, count, wastage")},
      {fieldname: "height", label: "Height", fieldtype: "Float"},
      {fieldname: "width", label: "Width", fieldtype: "Float"},
      {fieldname: "length", label: "Length", fieldtype: "Float"},
      {fieldname: "count", label: __("Count"), fieldtype: "Float", default: 1},
      {fieldname: "wastage", label: __("Wastage"), fieldtype: "Float", default: 1},
    ],
    primary_action_label: __("Compute"),
    primary_action(v) {
      frappe.call({
        method: "insite.api.test_measure",
        args: v,
        callback: (r) => frappe.msgprint(__("Result: {0}", [r.message])),
      });
    },
  });
  d.show();
}
