// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order Collection", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Submit Order"), () => {
				frm.call("submit_order").then(() => frm.reload_doc());
			}).addClass("btn-success agri-btn-main");
		}
		if (frm.doc.status !== "Draft" && !frm.doc.erp_synced
			&& frappe.user.has_role(["Agriculture Manager", "System Manager"])) {
			frm.add_custom_button(__("Push to SAP B1"), () => {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.push_order",
					args: { order_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Pushing to SAP B1..."),
				}).then(() => frm.reload_doc());
			}, __("Integration"));
		}
	},
});

// Auto-fill unit price from the default selling price list when an item is chosen
frappe.ui.form.on("Order Collection Item", {
	item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item) return;
		frappe.db.get_single_value("Agriculture Settings", "sap_default_price_list").then((price_list) => {
			if (!price_list) return;
			frappe.db.get_value("Item Price",
				{ item_code: row.item, price_list: price_list, selling: 1 },
				"price_list_rate"
			).then((r) => {
				if (r.message && r.message.price_list_rate) {
					frappe.model.set_value(cdt, cdn, "unit_price", r.message.price_list_rate);
				}
			});
		});
		// Default the product name from the item
		frappe.db.get_value("Item", row.item, "item_name").then((r) => {
			if (r.message && r.message.item_name && !row.product_name) {
				frappe.model.set_value(cdt, cdn, "product_name", r.message.item_name);
			}
		});
	},
	quantity: calc_total,
	unit_price: calc_total,
});

function calc_total(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "total_value", (row.quantity || 0) * (row.unit_price || 0));
}
