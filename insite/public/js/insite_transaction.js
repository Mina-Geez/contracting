// Show the Insite dimension fields on item rows; recompute is server-side.
const INSITE_DIMS = ["custom_base_qty", "custom_height", "custom_width",
                     "custom_length", "custom_waste_factor"];

frappe.ui.form.on("Sales Order Item", {
  items_add(frm, cdt, cdn) {},
});

// Nudge users: after editing a dimension, save to recompute (server-authoritative).
function insite_mark_dirty(frm) { frm.dirty(); }
