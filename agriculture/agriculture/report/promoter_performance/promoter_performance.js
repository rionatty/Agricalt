frappe.query_reports["Promoter Performance"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
		  default: frappe.datetime.add_months(frappe.datetime.get_today(), -1) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
		  default: frappe.datetime.get_today() },
		{ fieldname: "promoter", label: __("Promoter"), fieldtype: "Link", options: "Field Promoter" },
		{ fieldname: "region", label: __("Region"), fieldtype: "Select",
		  options: ["", "Central", "Eastern", "Western", "Northern", "South-Western", "Other"] },
	],
};
