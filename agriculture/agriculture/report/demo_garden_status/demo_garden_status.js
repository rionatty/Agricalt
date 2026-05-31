frappe.query_reports["Demo Garden Status"] = {
	filters: [
		{ fieldname: "status", label: __("Status"), fieldtype: "Select",
		  options: ["", "Registered", "Material Requested", "Material Received", "Planted",
		            "Monitoring", "Field Day Scheduled", "Field Day Done", "Completed"] },
		{ fieldname: "promoter", label: __("Promoter"), fieldtype: "Link", options: "Field Promoter" },
	],
};
