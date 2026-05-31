frappe.query_reports["Farmer Visit History"] = {
	filters: [
		{ fieldname: "farmer", label: __("Farmer"), fieldtype: "Link", options: "Farmer" },
		{ fieldname: "promoter", label: __("Promoter"), fieldtype: "Link", options: "Field Promoter" },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
		  default: frappe.datetime.add_months(frappe.datetime.get_today(), -1) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
		  default: frappe.datetime.get_today() },
	],
};
