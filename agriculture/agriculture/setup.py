import frappe
from frappe import _


def insert_record(records):
	"""Local replacement for the removed erpnext.setup.utils.insert_record."""
	for record in records:
		doc = frappe.get_doc(record)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_if_duplicate = True
		try:
			doc.insert()
		except frappe.DuplicateEntryError:
			pass


ALL_ROLES = ["Agriculture Manager", "Agriculture User", "Store Manager", "Marketing Manager"]


def setup_agriculture():
	create_roles()
	ensure_custom_fields()
	if frappe.get_all("Agriculture Analysis Criteria"):
		# data already seeded; still ensure permissions are in place
		add_additional_permissions()
		add_store_manager_permissions()
		grant_oversight_permissions()
		grant_system_manager_permissions()
		return
	create_agriculture_data()
	add_additional_permissions()
	add_store_manager_permissions()
	grant_oversight_permissions()
	grant_system_manager_permissions()


def create_roles():
	"""Create all Agriculture roles if they don't exist."""
	for role_name in ALL_ROLES:
		if not frappe.db.exists("Role", role_name):
			frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert()
	frappe.db.commit()


def ensure_custom_fields():
	"""Custom fields needed to map ERPNext masters back to SAP B1."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({
		"Customer": [
			{
				"fieldname": "sap_card_code",
				"label": "SAP B1 Card Code",
				"fieldtype": "Data",
				"insert_after": "customer_name",
				"unique": 0,
				"read_only": 0,
				"in_standard_filter": 1,
				"description": "Business Partner CardCode in SAP Business One",
			}
		],
		"Item": [
			{
				"fieldname": "sap_synced",
				"label": "Synced from SAP B1",
				"fieldtype": "Check",
				"insert_after": "item_group",
				"read_only": 1,
			}
		],
	}, ignore_validate=True)

def create_agriculture_data():
	records = [
		dict(
			doctype='Item Group',
			item_group_name='Fertilizer',
			is_group=0,
			parent_item_group=_('All Item Groups')),
		dict(
			doctype='Item Group',
			item_group_name='Seed',
			is_group=0,
			parent_item_group=_('All Item Groups')),
		dict(
			doctype='Item Group',
			item_group_name='By-product',
			is_group=0,
			parent_item_group=_('All Item Groups')),
		dict(
			doctype='Item Group',
			item_group_name='Produce',
			is_group=0,
			parent_item_group=_('All Item Groups')),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Nitrogen Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Phosphorous Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Potassium Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Calcium Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Sulphur Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Magnesium Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Iron Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Copper Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Zinc Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Boron Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Manganese Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Chlorine Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Molybdenum Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Sodium Content',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Humic Acid',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Fulvic Acid',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Inert',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Others',
			standard=1,
			linked_doctype='Fertilizer'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Nitrogen',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Phosphorous',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Potassium',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Calcium',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Magnesium',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Sulphur',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Boron',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Copper',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Iron',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Manganese',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Zinc',
			standard=1,
			linked_doctype='Plant Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Depth (in cm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Soil pH',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Salt Concentration (%)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Organic Matter (%)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='CEC (Cation Exchange Capacity) (MAQ/100mL)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Potassium Saturation (%)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Calcium Saturation (%)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Manganese Saturation (%)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Nirtogen (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Phosphorous (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Potassium (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Calcium (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Magnesium (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Sulphur (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Copper (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Iron (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Manganese (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Zinc (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Aluminium (ppm)',
			standard=1,
			linked_doctype='Soil Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Water pH',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Conductivity (mS/cm)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Hardness (mg/CaCO3)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Turbidity (NTU)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Odor',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Color',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Nitrate (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Nirtite (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Calcium (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Magnesium (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Sulphate (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Boron (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Copper (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Iron (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Manganese (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Zinc (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Chlorine (mg/L)',
			standard=1,
			linked_doctype='Water Analysis'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Bulk Density',
			standard=1,
			linked_doctype='Soil Texture'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Field Capacity',
			standard=1,
			linked_doctype='Soil Texture'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Wilting Point',
			standard=1,
			linked_doctype='Soil Texture'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Hydraulic Conductivity',
			standard=1,
			linked_doctype='Soil Texture'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Organic Matter',
			standard=1,
			linked_doctype='Soil Texture'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Temperature High',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Temperature Low',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Temperature Average',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Dew Point',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Precipitation Received',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Humidity',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Pressure',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Insolation/ PAR (Photosynthetically Active Radiation)',
			standard=1,
			linked_doctype='Weather'),
		dict(
			doctype='Agriculture Analysis Criteria',
			title='Degree Days',
			standard=1,
			linked_doctype='Weather')
	]
	insert_record(records)

def _ensure_docperm(parent, role, perms):
	"""Insert a Custom DocPerm for (parent, role) only if one doesn't exist.

	Guards against duplicate permission rows when setup runs more than once
	(e.g. re-install or a re-run of after_install on an already-seeded site).
	"""
	if frappe.db.exists("Custom DocPerm", {"parent": parent, "role": role}):
		return
	frappe.get_doc(dict(doctype="Custom DocPerm", parent=parent, role=role, **perms)).insert()


def add_additional_permissions():
	_ensure_docperm("Location", "Agriculture Manager", {
		"create": 1, "delete": 1, "email": 1, "export": 1, "print": 1,
		"read": 1, "report": 1, "share": 1, "write": 1,
	})
	_ensure_docperm("Location", "Agriculture User", {
		"email": 1, "export": 1, "print": 1, "read": 1, "report": 1,
		"share": 1, "write": 1,
	})

def add_store_manager_permissions():
	"""Grant Store Manager read + write access to Demo Garden Material Request."""
	if frappe.db.exists("Custom DocPerm", {"parent": "Demo Garden Material Request", "role": "Store Manager"}):
		return
	frappe.get_doc({
		"doctype": "Custom DocPerm",
		"parent": "Demo Garden Material Request",
		"role": "Store Manager",
		"read": 1, "write": 1, "email": 1, "print": 1,
	}).insert()


OVERSIGHT_ROLES = ["Marketing Manager", "Store Manager"]
OVERSIGHT_DOCTYPES = [
	"Field Activity Log", "Activity Plan", "Demo Garden",
	"Demo Garden Material Request", "Demo Garden Planting Record",
	"Demo Garden Input Application", "Demo Garden Monitoring Visit",
	"Demo Garden Field Day", "Farmer Training Event", "Order Collection",
	"Promoter Stock Ledger", "Promoter KPI Target", "Field Promoter", "Farmer",
]


def grant_oversight_permissions():
	"""Marketing Manager & Store Manager are treated as see-all roles in
	permissions.py (FULL_ACCESS_ROLES). Give them read-level DocPerms so that
	row-level visibility actually resolves to records they can open. Existing
	stronger perms (e.g. Store Manager write on Material Request) are preserved
	because _ensure_docperm skips a (doctype, role) that already exists."""
	read_perms = {"read": 1, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1}
	for dt in OVERSIGHT_DOCTYPES:
		for role in OVERSIGHT_ROLES:
			_ensure_docperm(dt, role, read_perms)


def grant_system_manager_permissions():
	"""System Manager was omitted from the custom doctypes' permissions, so a
	System-Manager admin who is not the literal Administrator has no create/edit
	access (the '+ Add' button disappears). Ensure the admin role can fully
	manage every Agriculture doctype."""
	full = {
		"read": 1, "write": 1, "create": 1, "delete": 1,
		"report": 1, "print": 1, "export": 1, "email": 1, "share": 1,
	}
	for dt in OVERSIGHT_DOCTYPES + ["Promoter Task"]:
		_ensure_docperm(dt, "System Manager", full)


def cleanup_role_and_permissions():
	for role in ALL_ROLES:
		frappe.db.delete("Custom DocPerm", {"role": role})
		if frappe.db.exists("Role", role):
			frappe.db.delete("Role", role)
	frappe.db.commit()
