# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PromoterStockLedger(Document):
	pass


@frappe.whitelist()
def get_promoter_stock_balance(promoter, demo_garden=None):
	"""Return current stock balance per product for a promoter."""
	filters = {"promoter": promoter}
	if demo_garden:
		filters["demo_garden"] = demo_garden

	ledger = frappe.get_all(
		"Promoter Stock Ledger",
		filters=filters,
		fields=["product_name", "uom", "qty_in", "qty_out", "balance_qty", "transaction_date"],
		order_by="product_name, transaction_date",
	)

	# Summarise per product — latest balance
	balances = {}
	for entry in ledger:
		balances[entry.product_name] = {
			"product_name": entry.product_name,
			"uom": entry.uom,
			"balance_qty": entry.balance_qty,
		}
	return list(balances.values())
