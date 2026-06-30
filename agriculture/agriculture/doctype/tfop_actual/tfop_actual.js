// Copyright (c) 2026, CyveTech and contributors
// For license information, please see license.txt

frappe.ui.form.on("TFOP Actual", {
	onload(frm) {
		// When launched from a TFOP ("Post Actual" button), preset the campaign,
		// which fires the tfop handler below to load the lines.
		if (frm.is_new() && frappe.route_options && frappe.route_options.tfop) {
			frm.set_value("tfop", frappe.route_options.tfop);
			frappe.route_options = null;
		}
		// Only offer requisitions/requests for the same campaign as a reference.
		const sameTfop = () => ({ filters: { tfop: frm.doc.tfop || "" } });
		frm.set_query("cash_requisition", sameTfop);
		frm.set_query("marketing_material_request", sameTfop);
	},

	tfop(frm) {
		// Selecting a campaign loads its budget lines into the actual tables so
		// the user only types the actual against each line.
		if (!frm.doc.tfop) return;
		frappe.db.get_doc("TFOP", frm.doc.tfop).then((tfop) => {
			frm.clear_table("product_actuals");
			frm.clear_table("activity_actuals");
			frm.clear_table("material_actuals");
			frm.clear_table("other_actuals");

			(tfop.products || []).forEach((r) => {
				const row = frm.add_child("product_actuals");
				row.item_code = r.item_code;
				row.item_name = r.item_name;
				row.budget_amount = r.line_total;
			});
			(tfop.activities || []).forEach((r) => {
				const row = frm.add_child("activity_actuals");
				row.activity = r.activity;
				row.budget_amount = r.amount;
			});
			(tfop.marketing_materials || []).forEach((r) => {
				const row = frm.add_child("material_actuals");
				row.item = r.item;
				row.item_name = r.item_name;
				row.budget_amount = r.amount;
			});
			(tfop.other_costs || []).forEach((r) => {
				const row = frm.add_child("other_actuals");
				row.cost_description = r.cost_description;
				row.budget_amount = r.amount;
			});

			frm.refresh_fields();
			frappe.show_alert({
				message: __("Budget lines loaded — enter the actuals against each."),
				indicator: "green",
			});
		});
	},

	validate(frm) {
		let total = 0;
		["product_actuals", "activity_actuals", "material_actuals", "other_actuals"].forEach((t) => {
			(frm.doc[t] || []).forEach((r) => {
				total += flt(r.actual_amount);
			});
		});
		frm.set_value("total_actual", total);
	},
});
