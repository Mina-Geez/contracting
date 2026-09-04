// Insite — transaction lines.
//
// The server decides the quantity when the document is saved. This script
// keeps the person entering the document from working blind until then: it
// asks which measurement boxes the line needs, shows the quantity as they
// type, offers only the scopes that belong to this project, and carries the
// scope down to the next line.

const INSITE_MEASUREMENT_FIELDS = [
	"custom_base_qty",
	"custom_height",
	"custom_width",
	"custom_length",
	"custom_waste_factor",
];

// Quantities are derived on these. A purchase line carries the Scope for cost,
// but its quantity is what was ordered, so nothing here may touch it.
const INSITE_MEASURED_DOCTYPES = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"];

const INSITE_BUYING_DOCTYPES = [
	"Material Request",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
];

const INSITE_PARENT_DOCTYPES = INSITE_MEASURED_DOCTYPES.concat(INSITE_BUYING_DOCTYPES);

function insite_refresh_line(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row || !row.item_code) return;

	const values = {};
	INSITE_MEASUREMENT_FIELDS.forEach((fieldname) => {
		values[fieldname] = row[fieldname] || 0;
	});

	frappe.call({
		method: "insite.api.line_preview",
		args: { item_code: row.item_code, values: values },
		callback(r) {
			const answer = r.message;
			if (!answer) return;
			frappe.model.set_value(cdt, cdn, "custom_measurement_inputs", answer.inputs);
			if (answer.quantity !== null && answer.quantity !== undefined) {
				frappe.model.set_value(cdt, cdn, "qty", answer.quantity);
			}
		},
	});
}

// Never offer a scope from another project: the document would be refused on
// save, and the picker should not have suggested it.
//
// `scope_item` is an Accounting Dimension, so ERPNext puts its own query on the
// field. Two separate things went wrong here, and only the second was visible
// without a browser. First, that query silently replaced a plain
// `frm.set_query`, so we wrap it instead of replacing it. Second, ERPNext's
// query cannot narrow by project at all, so wrapping alone still offered every
// scope in the company — hence the delegation to `insite.api.scope_query`.
// The marker lets us notice if ERPNext replaces the field's query again later.
function insite_narrow_scope_to_project(frm) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;

	const field = grid.get_field("scope_item");
	if (!field || (field.get_query && field.get_query.__insite)) return;

	const original = field.get_query;
	const wrapped = function (doc, cdt, cdn) {
		const base = original ? original.call(this, doc, cdt, cdn) || {} : {};
		if (!frm.doc.project) return base;

		// ERPNext's own values win over these defaults; the project always wins.
		// The defaults matter on the Quotation, where the Scope field is
		// Insite's own and carries no ERPNext query — without a company,
		// `get_filtered_dimensions` filters on `company = None` and the picker
		// comes back empty.
		const filters = Object.assign(
			{ dimension: "scope_item", account: "", company: frm.doc.company },
			base.filters,
			{ project: frm.doc.project }
		);
		// A project filter handed to ERPNext's dimension search does nothing:
		// it reads the dimension, the account and the company out of the
		// filters and ignores every other key. Browser testing found the picker
		// still offering all 314 scopes across four projects. So point it at
		// Insite's search, which runs ERPNext's and then keeps the scopes that
		// are on this project.
		return Object.assign({}, base, { query: "insite.api.scope_query", filters: filters });
	};
	wrapped.__insite = true;
	field.get_query = wrapped;
}

// Who the selling document is for. A Sales Order, Delivery Note and Sales
// Invoice each carry a `customer`. A Quotation does not: it has a party, and
// that party is only a customer when `quotation_to` says so — it may equally be
// a Lead or a Prospect, and a lead has no projects to offer.
function insite_selling_customer(doc) {
	if (doc.customer) return doc.customer;
	if (doc.quotation_to === "Customer") return doc.party_name;
	return null;
}

// Never offer another customer's project.
//
// ERPNext already does this on the Sales Order, Delivery Note and Sales
// Invoice: `get_project_name` matches the customer, and deliberately also
// allows projects with no customer set, since the field is not mandatory and a
// site that leaves it blank would otherwise get an empty picker. Nothing to
// rebuild — but it reads `doc.customer`, and a Quotation has no such field, so
// on a Quotation it narrowed nothing. The Project on a Quotation is Insite's
// own field anyway, so nothing had put a query on it at all.
function insite_narrow_project_to_customer(frm) {
	const field = frm.fields_dict && frm.fields_dict.project;
	if (!field || (field.get_query && field.get_query.__insite)) return;

	const original = field.get_query;
	const wrapped = function (doc) {
		const base = original ? original.call(this, doc) || {} : {};
		const customer = insite_selling_customer(frm.doc);
		if (!customer) return base; // a lead or a prospect: every project is fair game

		return Object.assign({}, base, {
			query: base.query || "erpnext.controllers.queries.get_project_name",
			filters: Object.assign({}, base.filters, {
				customer: customer,
				company: frm.doc.company,
			}),
		});
	};
	wrapped.__insite = true;
	field.get_query = wrapped;
}

INSITE_PARENT_DOCTYPES.forEach((parent) => {
	const child = `${parent} Item`;
	const selling = INSITE_MEASURED_DOCTYPES.includes(parent);

	const narrow = (frm) => {
		insite_narrow_scope_to_project(frm);
		// A supplier has no projects of their own, so this is a selling rule.
		if (selling) insite_narrow_project_to_customer(frm);
	};

	const parent_handlers = {
		onload: narrow,
		refresh: narrow,
		project: narrow,
		customer: narrow,
		party_name: narrow,
		quotation_to: narrow,
	};

	frappe.ui.form.on(parent, parent_handlers);

	const measured = INSITE_MEASURED_DOCTYPES.includes(parent);

	const handlers = {
		item_code(frm, cdt, cdn) {
			if (measured) insite_refresh_line(frm, cdt, cdn);
		},
		items_add(frm, cdt, cdn) {
			// Most lines on a document belong to the same scope. Carry it down
			// rather than making someone pick it forty times.
			const rows = frm.doc.items || [];
			const previous = rows[rows.length - 2];
			if (previous && previous.scope_item) {
				frappe.model.set_value(cdt, cdn, "scope_item", previous.scope_item);
			}
		},
	};

	if (measured) {
		INSITE_MEASUREMENT_FIELDS.forEach((fieldname) => {
			handlers[fieldname] = (frm, cdt, cdn) => insite_refresh_line(frm, cdt, cdn);
		});
	}

	frappe.ui.form.on(child, handlers);
});
