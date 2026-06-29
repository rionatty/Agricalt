// Copyright (c) 2026, CyveTech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Channel Stock Movement", {
	recalc_total(frm) {
		const total = (frm.doc.items || []).reduce((s, r) => s + flt(r.qty), 0);
		frm.set_value("total_qty", total);
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.stock_entry) {
			frm.add_custom_button(__("View Stock Entry"), () => {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}
	},
});

frappe.ui.form.on("Channel Stock Movement Item", {
	qty(frm) {
		frm.trigger("recalc_total");
	},
	items_remove(frm) {
		frm.trigger("recalc_total");
	},
});

frappe.listview_settings["Channel Stock Movement"] = {
	get_indicator(doc) {
		if (doc.docstatus === 2) return [__("Cancelled"), "red", "docstatus,=,2"];
		if (doc.docstatus === 1) return [__("Submitted"), "green", "docstatus,=,1"];
		return [__("Draft"), "gray", "docstatus,=,0"];
	},
};
