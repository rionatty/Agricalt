// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Agriculture Settings", {
	refresh(frm) {
		if (!frm.doc.sap_b1_enabled) return;

		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "agriculture.agriculture.sap_integration.test_connection",
				freeze: true,
				freeze_message: __("Connecting to SAP B1..."),
				callback: (r) => {
					if (r.message && r.message.ok) {
						frappe.msgprint({ title: __("Success"), indicator: "green",
							message: r.message.message });
					} else {
						frappe.msgprint({ title: __("Connection Failed"), indicator: "red",
							message: (r.message && r.message.message) || __("Unknown error") });
					}
				},
			});
		}, __("SAP B1"));

		const sync = (method, label) => {
			frappe.call({
				method: `agriculture.agriculture.sap_integration.${method}`,
				freeze: true,
				freeze_message: __("Syncing {0} from SAP B1...", [label]),
				callback: (r) => {
					frappe.show_alert({ message: __("{0} sync complete", [label]), indicator: "green" });
					frm.reload_doc();
				},
			});
		};

		frm.add_custom_button(__("Sync Items"), () => sync("pull_items", "Items"), __("SAP B1"));
		frm.add_custom_button(__("Sync Customers"), () => sync("pull_customers", "Customers"), __("SAP B1"));
		frm.add_custom_button(__("Sync Price Lists"), () => sync("pull_price_lists", "Price Lists"), __("SAP B1"));

		frm.add_custom_button(__("Sync All Masters"), () => {
			frappe.confirm(__("Pull all Items, Customers and Price Lists from SAP B1 now?"), () => {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.sync_masters_from_sap",
					freeze: true,
					freeze_message: __("Syncing all master data from SAP B1..."),
					callback: (r) => {
						const m = r.message || {};
						frappe.msgprint({
							title: __("SAP B1 Master Sync Complete"), indicator: "green",
							message: __("Price Lists: {0}<br>Items: {1}<br>Customers: {2}",
								[m.price_lists || 0, m.items || 0, m.customers || 0]),
						});
						frm.reload_doc();
					},
				});
			});
		}, __("SAP B1")).addClass("btn-success agri-btn-main");
	},
});
