// Insite — Work Item Type.
//
// A kind of work is not much use until it has a rule saying how it is
// measured, so the form says so and offers to make one.

frappe.ui.form.on("Work Item Type", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Add a Measurement Rule"), () => {
			frappe.new_doc("Measurement Rule", { work_item_type: frm.doc.name });
		});

		frappe.db
			.count("Measurement Rule", { filters: { work_item_type: frm.doc.name } })
			.then((count) => {
				// Clear first: refresh runs again after every save, and the
				// headline is added, not replaced — so without this the nudge
				// stacks up, and it would still be there after the rule that
				// answers it has been written.
				frm.dashboard.clear_headline();
				if (count) return;
				frm.dashboard.set_headline(
					__(
						"Nothing is measured yet. Add a Measurement Rule to say how {0} work is worked out.",
						[frm.doc.name]
					)
				);
			});
	},
});
