frappe.query_reports["Materials Issued vs Applied"] = {
	filters: [
		{ fieldname: "promoter", label: __("Promoter"), fieldtype: "Link", options: "Field Promoter" },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
	],
};
