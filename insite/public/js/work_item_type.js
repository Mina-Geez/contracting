// Insite — Work Item Type.
//
// "Test a Measure" lets someone check a rule with sample numbers before any
// real document relies on it. The arithmetic is done on the server, by the same
// code that runs on a live document, so what you see here is what you get.

const INSITE_MEASURES = [
	"Area (Height × Width × Count)",
	"Perimeter ((Height + Width) × 2 × Count)",
	"Linear (Length × Count)",
	"Count",
	"Piece × Wastage (Count × Wastage)",
	"Custom formula",
];

frappe.ui.form.on("Work Item Type", {
	refresh(frm) {
		frm.add_custom_button(__("Test a Measure"), () => insite_test_measure_dialog());
	},
});

function insite_test_measure_dialog() {
	const dialog = new frappe.ui.Dialog({
		title: __("Test a Measure"),
		fields: [
			{
				fieldname: "measure",
				label: __("Measured By"),
				fieldtype: "Select",
				options: INSITE_MEASURES.join("\n"),
				default: INSITE_MEASURES[0],
				reqd: 1,
			},
			{
				fieldname: "formula",
				label: __("Custom formula"),
				fieldtype: "Data",
				depends_on: "eval:doc.measure=='Custom formula'",
				description: __("Words you can use: height, width, length, count, wastage."),
			},
			{ fieldname: "height", label: __("Height"), fieldtype: "Float" },
			{ fieldname: "width", label: __("Width"), fieldtype: "Float" },
			{ fieldname: "length", label: __("Length"), fieldtype: "Float" },
			{ fieldname: "column_break", fieldtype: "Column Break" },
			{ fieldname: "count", label: __("Count"), fieldtype: "Float", default: 1 },
			{
				fieldname: "wastage",
				label: __("Wastage"),
				fieldtype: "Float",
				description: __("A multiplier. Type 1.1 to add 10 percent. Leave blank for none."),
			},
		],
		primary_action_label: __("Work it out"),
		primary_action(values) {
			frappe.call({
				method: "insite.api.preview_measure",
				args: values,
				callback(response) {
					const quantity = response.message;
					dialog.set_df_property(
						"measure",
						"description",
						quantity === null
							? __("This measure keeps the quantity you type on the line.")
							: __("Quantity: {0}", [format_number(quantity)])
					);
				},
			});
		},
	});
	dialog.show();
}
