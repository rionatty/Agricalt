// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Agriculture Settings", {
	refresh(frm) {
		if (!frm.doc.sap_b1_enabled) return;

		// ── Test connection ───────────────────────────────────────────────────
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "agriculture.agriculture.sap_integration.test_connection",
				freeze: true,
				freeze_message: __("Connecting to SAP B1…"),
				callback(r) {
					const res = r.message || {};
					frappe.msgprint({
						title: res.ok ? __("Connected") : __("Connection Failed"),
						indicator: res.ok ? "green" : "red",
						message: res.message || __("Unknown error"),
					});
				},
			});
		}, __("SAP B1"));

		// ── Individual sync buttons (all run in background) ───────────────────
		const sync_bg = (method, label) => {
			frappe.call({
				method: `agriculture.agriculture.sap_integration.${method}`,
				freeze: true,
				freeze_message: __("Queuing {0} sync…", [label]),
				callback(r) {
					const res = r.message || {};
					frappe.show_alert({ message: res.message || __("{0} sync queued", [label]), indicator: "green" }, 8);
					// Auto-open Sync Log after 3 seconds so user can watch progress
					setTimeout(() => {
						frappe.set_route("List", "SAP B1 Sync Log", {});
					}, 3000);
				},
			});
		};

		frm.add_custom_button(__("Sync Price Lists"), () => sync_bg("enqueue_pull_price_lists", "Price Lists"), __("SAP B1"));
		frm.add_custom_button(__("Sync Customers"),   () => sync_bg("enqueue_pull_customers",   "Customers"),   __("SAP B1"));
		frm.add_custom_button(__("Sync Items"),       () => sync_bg("enqueue_pull_items",       "Items"),       __("SAP B1"));

		// ── Sync All (primary green button) ──────────────────────────────────
		frm.add_custom_button(__("🔄 Sync All Masters"), () => {
			frappe.confirm(
				__("Pull all Items, Customers and Price Lists from SAP B1 now?<br><br>"
				 + "<b>This runs in the background</b> — you will be notified via SAP B1 Sync Log when done."),
				() => {
					frappe.call({
						method: "agriculture.agriculture.sap_integration.enqueue_sync_all",
						freeze: true,
						freeze_message: __("Starting background sync…"),
						callback(r) {
							const res = r.message || {};
							frappe.msgprint({
								title: __("Sync Started"),
								indicator: "green",
								message: res.message || __("Background sync queued. Check SAP B1 Sync Log for results."),
							});
							// Redirect to Sync Log so user can monitor
							setTimeout(() => frappe.set_route("List", "SAP B1 Sync Log", {}), 2000);
						},
					});
				}
			);
		}, __("SAP B1")).addClass("btn-success agri-btn-main");

		// ── Sync Log shortcut ─────────────────────────────────────────────────
		frm.add_custom_button(__("View Sync Log"), () => {
			frappe.set_route("List", "SAP B1 Sync Log", {});
		}, __("SAP B1"));
	},
});
