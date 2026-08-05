// Agriculture App — global JS
// Adds status indicator colours across all Agriculture doctypes

frappe.provide("agriculture");

// Map status text → Frappe indicator color
const STATUS_COLORS = {
	// Generic workflow
	"Draft":              "gray",
	"Submitted":          "blue",
	"Approved":           "green",
	"Rejected":           "red",
	"Cancelled":          "red",
	"Completed":          "green",
	"Open":               "orange",
	"In Progress":        "blue",
	// Material / dispatch
	"Issued":             "orange",
	"Received":           "green",
	"Processed in ERP":   "purple",
	// Demo garden lifecycle
	"Registered":         "gray",
	"Material Requested": "yellow",
	"Material Received":  "blue",
	"Planted":            "green",
	"Monitoring":         "cyan",
	"Field Day Scheduled":"orange",
	"Field Day Done":     "green",
	// Events
	"Planned":            "yellow",
	"Active":             "green",
	"Inactive":           "gray",
	// SAP Sync
	"Pending":            "yellow",
	"Success":            "green",
	"Failed":             "red",
};

agriculture.get_status_color = (status) => STATUS_COLORS[status] || "gray";

// Apply indicator dot to the status field on every form
const AGRI_DOCTYPES = [
	"Activity Plan", "Field Activity Log", "Demo Garden",
	"Demo Garden Material Request", "Demo Garden Planting Record",
	"Demo Garden Input Application", "Demo Garden Monitoring Visit",
	"Demo Garden Field Day", "Farmer Training Event",
	"Order Collection", "Promoter Stock Ledger", "Promoter KPI Target",
	"Promoter Task", "Field Promoter", "SAP B1 Sync Log",
];

AGRI_DOCTYPES.forEach((dt) => {
	frappe.ui.form.on(dt, {
		refresh(frm) {
			const status = frm.doc.status;
			if (!status) return;
			const color = agriculture.get_status_color(status);
			frm.page.set_indicator(status, color);
		},
	});
});
