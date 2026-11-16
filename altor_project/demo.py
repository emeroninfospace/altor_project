# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Demo data built from the client's ERP_Comments sheet, for presentations and testing.

    bench --site <site> execute altor_project.demo.make_demo_data
    bench --site <site> execute altor_project.demo.delete_demo_data
    bench --site <site> execute altor_project.demo.reset_demo_data     # delete + make

All are whitelisted for System Managers; pass background=1 to run them as a background job and
read the result with altor_project.demo.demo_status.

Client data (kept by delete_demo_data, as these are the client's own masters):
  customers (Customer Master sheet), the scaffolding division's standard quotation lines, the
  asset list (Asset list sheet), the budget cost lines (Budget), the cross hire items of the
  Rental PO sheets and the two workers of the overtime calculation (Aswin, Manu).
Demo transactions (names / remarks start with "DEMO", removed by delete_demo_data):
  one Lead -> Quotation -> Sales Order -> Project chain per division, budgets, the three rental
  (cross hire) purchase orders exactly as in the sheets, opening Project Assets with sample
  quantities and costs, asset issues / returns (with damage), Aswin's and Manu's November
  Timesheets exactly as in the overtime sheet, transport / inspection / consumables bills,
  the agency bill and a sales invoice.

Every step is independent: if one fails it is reported and the rest still runs.
"""

import random
from contextlib import contextmanager
from datetime import timedelta

import frappe
from frappe.model import default_fields
from frappe.utils import add_days, cint, flt, get_datetime, getdate, nowdate

PREFIX = "DEMO"
ASSET_REMARK = f"{PREFIX} opening stock (sample quantity and cost)"
RESULT_KEY = "altor_demo_result"

# ---------------------------------------------------------------------------
# Client data (ERP_Comments.xlsx)
# ---------------------------------------------------------------------------

# division name, division code used when the Cost Center is created
DIVISIONS = {"scf": ("Scaffolding", "SCF"), "crd": ("Cradle", "CRD"), "eqr": ("Equipment Rental", "EQR")}

# Budget sheet: cost lines of a project budget (Item Groups). "Material Cost" holds the asset groups.
COST_GROUPS = [
	"Manpower Cost",
	"Outsource Manpower Cost",
	"Material Cost",
	"Cross Hire Material / Equipment Cost",
	"Manpower Transportation",
	"Material Transportation",
	"Third Party Inspection Charges",
	"Consumables",
	"Others",
]
ASSET_GROUPS = [
	"Scaffolding Materials",
	"Cradle",
	"Scissor Lift",
	"Boom Lift",
	"Construction Hoist",
	"Mast Climber",
	"Tower Crane",
]
SERVICE_GROUPS = {"scf": "Scaffolding Services", "crd": "Cradle Services", "eqr": "Equipment Rental Services"}

# code, name, uom: the scaffolding division's standard quotation lines (sheet 1), and the other divisions
SALES_ITEMS = {
	"scf": [
		("SCF-SRV-001", "Design and Calculation Charges", "Nos"),
		("SCF-SRV-002", "Third Party Design Review", "Nos"),
		("SCF-SRV-003", "Erection and Dismantling Charges", "Nos"),
		("SCF-SRV-004", "Hire Charges", "Week"),
		("SCF-SRV-005", "Third Party Inspection Charges", "Nos"),
		("SCF-SRV-006", "Scaff Tag Renewal Charges", "Nos"),
		("SCF-SRV-007", "Mob Demob Charges", "Nos"),
	],
	"crd": [
		("CRD-SRV-001", "Cradle Installation and Dismantling Charges", "Nos"),
		("CRD-SRV-002", "Cradle Hire Charges", "Week"),
		("CRD-SRV-003", "Cradle Operator Charges", "Day"),
		("CRD-SRV-004", "Mob Demob Charges (Cradle)", "Nos"),
	],
	"eqr": [
		("EQR-SRV-001", "Equipment Hire Charges", "Day"),
		("EQR-SRV-002", "Equipment Operator Charges", "Day"),
		("EQR-SRV-003", "Mob Demob Charges (Equipment)", "Nos"),
	],
}

# Asset list sheet. code, name, group, uom, sample unit cost (AED), depreciation months,
# sample opening qty, division key. Costs and quantities are samples, not from the client.
ASSET_ITEMS = [
	(
		"AST-SCF-001",
		"Cuplock Standard 3.0mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		95,
		60,
		1500,
		"scf",
	),
	(
		"AST-SCF-002",
		"Cuplock Standard 2.5mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		80,
		60,
		800,
		"scf",
	),
	(
		"AST-SCF-003",
		"Cuplock Standard 2.0mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		65,
		60,
		800,
		"scf",
	),
	(
		"AST-SCF-004",
		"Cuplock Ledger 2.5mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		45,
		60,
		1200,
		"scf",
	),
	(
		"AST-SCF-005",
		"Cuplock Ledger 1.8mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		34,
		60,
		900,
		"scf",
	),
	(
		"AST-SCF-006",
		"Cuplock Ledger 1.3mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		26,
		60,
		600,
		"scf",
	),
	(
		"AST-SCF-007",
		"Cuplock Ledger 1.0mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		21,
		60,
		500,
		"scf",
	),
	(
		"AST-SCF-008",
		"Cuplock Ledger 0.9mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		19,
		60,
		400,
		"scf",
	),
	("AST-SCF-009", "Spigot Connector with Nut & Bolt", "Scaffolding Materials", "Nos", 9, 60, 1500, "scf"),
	(
		"AST-SCF-010",
		"Bracing Tube 48.3 ODx3.2mm x 4.0mtr",
		"Scaffolding Materials",
		"Nos",
		75,
		60,
		400,
		"scf",
	),
	(
		"AST-SCF-011",
		"Bracing Tube 48.3 ODx3.2mm x 3.5mtr",
		"Scaffolding Materials",
		"Nos",
		66,
		60,
		300,
		"scf",
	),
	(
		"AST-SCF-012",
		"Bracing Tube 48.3 ODx3.2mm x 3.0mtr",
		"Scaffolding Materials",
		"Nos",
		57,
		60,
		300,
		"scf",
	),
	(
		"AST-SCF-013",
		"Bracing Tube 48.3 ODx3.2mm x 2.5mtr",
		"Scaffolding Materials",
		"Nos",
		48,
		60,
		300,
		"scf",
	),
	(
		"AST-SCF-014",
		"Bracing Tube 48.3 ODx3.2mm x 2.0mtr",
		"Scaffolding Materials",
		"Nos",
		39,
		60,
		300,
		"scf",
	),
	(
		"AST-SCF-015",
		"Bracing Tube 48.3 ODx3.2mm x 1.5mtr",
		"Scaffolding Materials",
		"Nos",
		30,
		60,
		300,
		"scf",
	),
	("AST-SCF-016", "Swivel Coupler - Drop Forged", "Scaffolding Materials", "Nos", 14, 60, 3000, "scf"),
	("AST-SCF-017", "Board Retaining Coupler (BRC)", "Scaffolding Materials", "Nos", 9, 60, 2000, "scf"),
	(
		"AST-SCF-018",
		"Intermediate Transom 1.3mtr (3.2mm, Painted)",
		"Scaffolding Materials",
		"Nos",
		30,
		60,
		600,
		"scf",
	),
	("AST-SCF-019", "Stair Case Ladder", "Scaffolding Materials", "Nos", 420, 60, 30, "scf"),
	("AST-SCF-020", "U-Head Jack", "Scaffolding Materials", "Nos", 38, 60, 400, "scf"),
	(
		"AST-CRD-001",
		"Cradle Set Suspended 6.0m Length, 100m Working Height Without Support",
		"Cradle",
		"Set",
		85000,
		84,
		6,
		"crd",
	),
	(
		"AST-SCL-001",
		"Electric Scissor Lift - Platform Height 9.8M, Working Height 11.8M, Capacity 350KG",
		"Scissor Lift",
		"Nos",
		65000,
		84,
		4,
		"eqr",
	),
	(
		"AST-SCL-002",
		"Electric Scissor Lift - Platform Height 11.8M, Working Height 13.8M, Capacity 350KG",
		"Scissor Lift",
		"Nos",
		78000,
		84,
		3,
		"eqr",
	),
	(
		"AST-SCL-003",
		"Electric Scissor Lift - Platform Height 5.8M, Working Height 7.8M, Capacity 250KG",
		"Scissor Lift",
		"Nos",
		42000,
		84,
		4,
		"eqr",
	),
	(
		"AST-BML-001",
		"Articulating Boom Lift - Platform Height 16M, Working Height 18M, 250/360KG, Lithium Battery",
		"Boom Lift",
		"Nos",
		210000,
		84,
		2,
		"eqr",
	),
	(
		"AST-BML-002",
		"Articulating Boom Lift - Platform Height 19.38M, Working Height 21.38M, 250/360KG, Lithium Battery",
		"Boom Lift",
		"Nos",
		260000,
		84,
		2,
		"eqr",
	),
	(
		"AST-HST-001",
		"Construction Hoist - Speed 0-50m/min, Double Cages, 200 Meters, Cable Pulley",
		"Construction Hoist",
		"Nos",
		380000,
		120,
		2,
		"eqr",
	),
	(
		"AST-HST-002",
		"Construction Hoist - Speed 0-63m/min, Double Cages, 200 Meters, Cable Pulley",
		"Construction Hoist",
		"Nos",
		420000,
		120,
		2,
		"eqr",
	),
	(
		"AST-MCL-001",
		"Single-Mast Work Platform - 50m Height Configuration",
		"Mast Climber",
		"Nos",
		300000,
		120,
		1,
		"eqr",
	),
	(
		"AST-MCL-002",
		"Twin-Mast Work Platform - 50m Height Configuration",
		"Mast Climber",
		"Nos",
		520000,
		120,
		1,
		"eqr",
	),
	(
		"AST-TWC-001",
		"Stationary Tower Crane - Po22b, 50m Jib Length, 10t Max Load",
		"Tower Crane",
		"Nos",
		1100000,
		120,
		1,
		"eqr",
	),
]

# Rental PO sheets (cross hire): project, supplier key, period, [(code, name, qty, uom, unit rate, periods)]
CROSS_HIRE_POS = [
	(
		"scf",
		"cross_hire_scaffold",
		"Week",
		[
			("XH-SCF-001", "Hire - Cuplock Standard 3.0mtr (3.2mm, Painted)", 100, "Nos", 0.5, 4),
			("XH-SCF-002", "Hire - Cuplock Standard 2.5mtr (3.2mm, Painted)", 40, "Nos", 0.43, 4),
			("XH-SCF-003", "Hire - Cuplock Standard 2.0mtr (3.2mm, Painted)", 50, "Nos", 0.37, 4),
			("XH-SCF-004", "Hire - Cuplock Ledger 2.5mtr (3.2mm, Painted)", 56, "Nos", 0.27, 4),
			("XH-SCF-005", "Hire - Cuplock Ledger 1.8mtr (3.2mm, Painted)", 42, "Nos", 0.19, 4),
			("XH-SCF-006", "Hire - Cuplock Ledger 1.3mtr (3.2mm, Painted)", 4, "Nos", 0.16, 4),
			("XH-SCF-007", "Hire - Cuplock Ledger 1.0mtr (3.2mm, Painted)", 55, "Nos", 0.15, 4),
			("XH-SCF-008", "Hire - Cuplock Ledger 0.9mtr (3.2mm, Painted)", 4, "Nos", 0.15, 4),
			("XH-SCF-009", "Hire - Spigot Connector with Nut & Bolt", 3, "Nos", 0.06, 4),
		],
	),
	(
		"crd",
		"cross_hire_cradle",
		"Week",
		[("XH-CRD-001", "Hire - Cradle 6.0m Length with all Accessories", 2, "Set", 375, 4)],
	),
	(
		"eqr",
		"cross_hire_equipment",
		"Day",
		[
			(
				"XH-SCL-001",
				"Hire - Scissor Lift Platform Height 8.0m & Working Height 10.0m",
				2,
				"Nos",
				125,
				10,
			)
		],
	),
]

# Purchased services charged to the project budget: code, name, cost group, uom
COST_ITEMS = [
	("SRV-MAT-TRN", "Material Transportation (Truck Trip)", "Material Transportation", "Nos"),
	("SRV-MP-TRN", "Manpower Transportation (Bus per Day)", "Manpower Transportation", "Day"),
	("SRV-TPI", "Third Party Inspection Visit", "Third Party Inspection Charges", "Nos"),
	("SRV-CONS", "Scaffolding Consumables (Tie Wire, Toe Board Clips, Tags)", "Consumables", "Nos"),
	("SRV-MPW-OUT", "Outsourced Manpower Service", "Outsource Manpower Cost", "Nos"),
]

# Customer Master sheet
CUSTOMERS = [
	{
		"code": 101,
		"name": "Al Tayer Stocks LLC",
		"license": "CN-12456",
		"trn": "1041500000006",
		"contact": ("Georgy", "Project Manager", "Georgysamuel@altayer.com", "+971504401604"),
		"accounts": ("Chandran", "accounts@altayerstocks.com"),
		"address": ("Ubora Towers, 42nd Floor", "Business Bay", "Dubai", "2623"),
		"terms": "30 Days Credit",
		"credit_limit": 250000,
	},
	{
		"code": 102,
		"name": "Perfect Step Maintenance and Contracting LLC",
		"license": "CN-24568",
		"trn": "1041500000006",
		"contact": ("Abhishek", "Project Engineer", "Abhishek@perfectuae.com", "+9715035578733"),
		"accounts": ("Ajith", "Ajith@perfectuae.com"),
		"address": ("Office No: 05, Plot No: 22", "M 26 - Mussafah", "Abu Dhabi", "34567"),
		"terms": "30 Days Credit",
		"credit_limit": 100000,
	},
	{
		"code": 103,
		"name": "Cylingas Engineering & Construction LLC",
		"license": "CN-799556",
		"trn": "1054654000004",
		"contact": ("Binu", "Construction Manager", "Binu@cylingas.com", "+971356757744764"),
		"accounts": ("Manu", "info@cylingasuae.com"),
		"address": ("30th Floor, Tiffany Tower", "Cluster W, JLT", "Dubai", "5650"),
		"terms": "Advance Payment",
		"credit_limit": 0,
	},
]
PAYMENT_TERMS = {"30 Days Credit": 30, "Advance Payment": 0}

# Calculations sheet: own staff (salary) and outsourced (hourly rate)
WORKERS = {
	"aswin": {
		"first_name": "Aswin",
		"designation": "Scaffolder",
		"custom_basic_salary": 1300,
		"custom_allowance": 400,
		"custom_hra": 0,
		"custom_transport_allowance": 0,
	},
	"manu": {
		"first_name": "Manu",
		"designation": "Scaffolder",
		"custom_is_outsourced": 1,
		"agency": "agency",
		"custom_hourly_cost_rate": 18,
	},
}
OT_MONTH = (2026, 11)
SUNDAYS = {1, 8, 15, 22, 29}
ABSENT = {19}


def sheet_hours(worker, day):
	"""(normal, OT 1, OT 2) of a day exactly as in the client's overtime sheet (None = absent)."""
	if day in ABSENT:
		return None
	if day in SUNDAYS:
		# the sheet books Manu 10 normal hours on Sundays except the 1st, Aswin none
		return (10 if worker == "manu" and day != 1 else 0, 0, 10)
	return (10, 2, 0) if worker == "manu" else (8, 2, 0)


SUPPLIERS = {
	"cross_hire_scaffold": f"{PREFIX} Gulf Scaffold Rentals LLC",
	"cross_hire_cradle": f"{PREFIX} Emirates Cradle Hire LLC",
	"cross_hire_equipment": f"{PREFIX} Al Quoz Access Equipment Rentals",
	"agency": f"{PREFIX} Star Manpower Supply Services",
	"transport": f"{PREFIX} Swift Transport LLC",
	"inspection": f"{PREFIX} Third Party Inspection Services",
	"consumables": f"{PREFIX} Builders Consumables Trading",
}

# One enquiry per division: Lead -> Quotation -> Sales Order -> Project.
# start / end: days from today; items: (code, qty, rate)
PROJECTS = {
	"scf": {
		"customer": 0,
		"name": f"{PREFIX} Ubora Towers Facade Scaffolding",
		"location": "Business Bay, Dubai",
		"scope": "Design, supply, erection and dismantling of cuplock scaffolding for the east facade, 26 weeks hire",
		"lpo": "LPO-AT-7781",
		"start": -32,
		"end": 150,
		"progress": 20,
		"items": [
			("SCF-SRV-001", 1, 3500),
			("SCF-SRV-002", 1, 1800),
			("SCF-SRV-003", 1, 24000),
			("SCF-SRV-004", 26, 4200),
			("SCF-SRV-005", 6, 650),
			("SCF-SRV-006", 26, 120),
			("SCF-SRV-007", 2, 1500),
		],
		# Budget sheet ("Others" is 0 and has no line)
		"budget": {
			"Manpower Cost": 60000,
			"Outsource Manpower Cost": 10000,
			"Material Cost": 10000,
			"Cross Hire Material / Equipment Cost": 5000,
			"Manpower Transportation": 5000,
			"Material Transportation": 5000,
			"Third Party Inspection Charges": 4000,
			"Consumables": 5000,
		},
		"tasks": [
			("Design & Calculation", 0.0, 0.05),
			("Third Party Design Review", 0.04, 0.08),
			("Mobilisation & Erection", 0.08, 0.2),
			("Hire Period & Inspections", 0.2, 0.9),
			("Dismantling & Demobilisation", 0.9, 1.0),
		],
	},
	"crd": {
		"customer": 1,
		"name": f"{PREFIX} Mussafah M-26 Building Cradle Hire",
		"location": "Mussafah, Abu Dhabi",
		"scope": "Supply, installation and dismantling of 2 suspended cradles 6.0m with operators, 12 weeks hire",
		"lpo": "LPO-PS-2290",
		"start": -15,
		"end": 70,
		"progress": 15,
		"items": [
			("CRD-SRV-001", 2, 6500),
			("CRD-SRV-002", 12, 2800),
			("CRD-SRV-003", 60, 350),
			("CRD-SRV-004", 2, 1200),
		],
		"budget": {
			"Manpower Cost": 15000,
			"Material Cost": 8000,
			"Cross Hire Material / Equipment Cost": 2500,
			"Material Transportation": 2000,
			"Third Party Inspection Charges": 1500,
			"Consumables": 1000,
		},
		"tasks": [
			("Mobilisation & Installation", 0.0, 0.12),
			("Hire Period", 0.12, 0.9),
			("Dismantling & Demobilisation", 0.9, 1.0),
		],
	},
	"eqr": {
		"customer": 2,
		"name": f"{PREFIX} Tiffany Tower JLT Access Equipment Rental",
		"location": "Cluster W, JLT, Dubai",
		"scope": "Rental of scissor lifts and an articulating boom lift with operators, 30 days",
		"lpo": "LPO-CY-0412",
		"start": -10,
		"end": 20,
		"progress": 35,
		"items": [("EQR-SRV-001", 90, 450), ("EQR-SRV-002", 30, 300), ("EQR-SRV-003", 2, 900)],
		"budget": {
			"Manpower Cost": 4000,
			"Material Cost": 6000,
			"Cross Hire Material / Equipment Cost": 3000,
			"Material Transportation": 1500,
		},
		"tasks": [("Delivery & Handover", 0.0, 0.1), ("Rental Period", 0.1, 0.95), ("Collection", 0.95, 1.0)],
	},
}

# Assets issued to the projects: project, days ago, [(asset item, qty)], returns [(days ago, item, good, damaged)]
ALLOCATIONS = [
	(
		"scf",
		30,
		[
			("AST-SCF-001", 400),
			("AST-SCF-002", 120),
			("AST-SCF-003", 150),
			("AST-SCF-004", 300),
			("AST-SCF-005", 160),
			("AST-SCF-006", 60),
			("AST-SCF-009", 200),
			("AST-SCF-010", 80),
			("AST-SCF-016", 600),
			("AST-SCF-017", 300),
			("AST-SCF-018", 120),
			("AST-SCF-019", 6),
			("AST-SCF-020", 80),
		],
		[(5, "AST-SCF-001", 100, 6), (5, "AST-SCF-016", 150, 12)],
	),
	("crd", 14, [("AST-CRD-001", 2)], []),
	("eqr", 10, [("AST-BML-001", 1), ("AST-SCL-001", 2)], []),
]

# Bills on the projects: project, supplier key, days ago, [(item, qty, rate)]
DIRECT_INVOICES = [
	("scf", "transport", 29, [("SRV-MAT-TRN", 6, 450)]),
	("scf", "transport", 10, [("SRV-MP-TRN", 20, 180)]),
	("scf", "inspection", 24, [("SRV-TPI", 2, 750)]),
	("scf", "consumables", 27, [("SRV-CONS", 2350, 1)]),
	("crd", "transport", 14, [("SRV-MAT-TRN", 2, 600)]),
	("crd", "inspection", 12, [("SRV-TPI", 1, 950)]),
	("eqr", "transport", 10, [("SRV-MAT-TRN", 2, 450)]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DemoLog:
	def __init__(self):
		self.created, self.errors = {}, []

	def add(self, doctype, name=None):
		self.created[doctype] = self.created.get(doctype, 0) + 1

	@contextmanager
	def step(self, title):
		savepoint = "demo_step"
		frappe.db.savepoint(savepoint)
		try:
			yield
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			frappe.clear_messages()
			self.errors.append(f"{title}: {frappe.utils.strip_html(str(e))[:300]}")
			frappe.log_error(title=f"Altor demo data: {title}")

	def result(self):
		return {"created": self.created, "errors": self.errors}


def _get_or_create(doctype, name, values, log, filters=None):
	existing = frappe.db.exists(doctype, filters or name)
	if existing:
		return existing if isinstance(existing, str) else name
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.flags.ignore_permissions = True
	doc.insert()
	log.add(doctype)
	return doc.name


def _first(doctype, filters=None, fallback=None):
	rows = frappe.get_all(doctype, filters=filters or {}, pluck="name", limit=1, order_by="creation asc")
	return rows[0] if rows else fallback


def _set_series(doc):
	"""Pick the first naming series option when the doctype uses one."""
	df = frappe.get_meta(doc.doctype).get_field("naming_series")
	if df and not doc.get("naming_series") and df.options:
		doc.naming_series = df.options.split("\n")[0]


def _insert(doc, log, submit=False):
	doc = frappe.get_doc(doc) if isinstance(doc, dict) else doc
	_set_series(doc)
	doc.flags.ignore_permissions = True
	doc.insert()
	if submit:
		doc.submit()
	log.add(doc.doctype)
	return doc


def _uom(name):
	return name if frappe.db.exists("UOM", name) else "Nos"


def _set_taxes(doc, template_doctype, ctx):
	"""Copy the company's 5% VAT template rows onto a document."""
	template = frappe.db.get_value(
		template_doctype, {"company": ctx.company, "title": ["like", "%VAT 5%"], "disabled": 0}, "name"
	)
	if not template:
		return
	doc.taxes_and_charges = template
	fields = (
		"charge_type",
		"account_head",
		"description",
		"rate",
		"cost_center",
		"category",
		"add_deduct_tax",
	)
	for t in frappe.get_doc(template_doctype, template).taxes:
		doc.append("taxes", {f: t.get(f) for f in fields if t.get(f) is not None})


def _cache():
	"""frappe.cache is an object in v15 and a function before."""
	cache = frappe.cache
	return cache if hasattr(cache, "set_value") else cache()


def _store_result(result):
	_cache().set_value(
		RESULT_KEY, {"finished_on": str(frappe.utils.now_datetime()), **result}, expires_in_sec=86400
	)
	return result


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _run(method, background, **kwargs):
	if cint(background):
		_cache().delete_value(RESULT_KEY)
		frappe.enqueue(f"altor_project.demo.{method}", queue="long", timeout=3600, **kwargs)
		return {"queued": True}
	return globals()[method](**kwargs)


@frappe.whitelist()
def make_demo_data(company=None, background=0):
	"""Create the demo data. Returns what was created and any step that failed."""
	frappe.only_for("System Manager")
	return _run("_make_demo_data", background, company=company)


@frappe.whitelist()
def delete_demo_data(background=0):
	"""Cancel and delete the demo transactions (and older DEMO records). Client masters are kept."""
	frappe.only_for("System Manager")
	return _run("_delete_demo_data", background)


@frappe.whitelist()
def reset_demo_data(company=None, background=0):
	"""delete_demo_data followed by make_demo_data."""
	frappe.only_for("System Manager")
	return _run("_reset_demo_data", background, company=company)


@frappe.whitelist()
def demo_status():
	"""Result of the last background run (None while it is still running)."""
	frappe.only_for("System Manager")
	return _cache().get_value(RESULT_KEY)


def _reset_demo_data(company=None):
	deleted = _delete_demo_data(store=False)
	made = _make_demo_data(company, store=False)
	return _store_result({"deleted": deleted, "made": made})


def _make_demo_data(company=None, store=True):
	random.seed(42)
	log = DemoLog()
	company = company or frappe.defaults.get_global_default("company") or _first("Company")
	if not company:
		frappe.throw("Create a Company first.")
	if frappe.db.exists("Project", {"project_name": PROJECTS["scf"]["name"]}):
		result = {"message": "Demo data already exists. Run delete_demo_data first.", **log.result()}
		return _store_result(result) if store else result

	frappe.flags.altor_skip_budget_update = True  # budgets are recalculated once at the end
	ctx = frappe._dict(
		company=company,
		abbr=frappe.get_cached_value("Company", company, "abbr"),
		today=getdate(nowdate()),
		divisions={},
		groups={},
		suppliers={},
		customers=[],
		workers={},
		projects={},
		sales_orders={},
		assets={},
		location=None,
	)
	for title, fn in (
		("Divisions", _make_divisions),
		("Asset accounting setup", _make_asset_setup),
		("Item groups", _make_item_groups),
		("Items", _make_items),
		("Payment terms", _make_payment_terms),
		("Customers", _make_customers),
		("Suppliers", _make_suppliers),
		("Altor Settings", _update_settings),
		("Workers", _make_workers),
	):
		with log.step(title):
			fn(ctx, log)
	for key in PROJECTS:
		with log.step(f"Sales flow and project ({DIVISIONS[key][0]})"):
			_make_sales_flow(ctx, log, key)
	for title, fn in (
		("Project budgets", _make_budgets),
		("Fixed assets (opening stock)", _make_assets),
		("Asset issues and returns", _make_allocations),
		("Cross hire purchase orders", _make_cross_hire_pos),
		("Project bills", _make_direct_invoices),
		("Timesheets (November overtime sheet)", _make_timesheets),
		("Agency bill", _make_agency_invoice),
		("Sales invoice", _make_sales_invoice),
		("Depreciation to projects (last month)", _post_depreciation_to_projects),
	):
		with log.step(title):
			fn(ctx, log)
	frappe.flags.altor_skip_budget_update = False
	with log.step("Budget figures"):
		from altor_project.assets import update_allocation
		from altor_project.budget import update_project_budget

		for name in frappe.get_all(
			"Asset Allocation",
			filters={"project": ["in", list(ctx.projects.values()) or [""]], "docstatus": 1},
			pluck="name",
		):
			update_allocation(name)
		for project in ctx.projects.values():
			update_project_budget(project)
	result = log.result()
	return _store_result(result) if store else result


# ---------------------------------------------------------------------------
# Masters (client data)
# ---------------------------------------------------------------------------


def _make_divisions(ctx, log):
	root = frappe.db.get_value(
		"Cost Center", {"company": ctx.company, "is_group": 1, "parent_cost_center": ["in", ["", None]]}
	)
	for key, (name, code) in DIVISIONS.items():
		existing = frappe.db.get_value(
			"Cost Center", {"company": ctx.company, "cost_center_name": name, "is_group": 0}
		)
		ctx.divisions[key] = (
			existing
			or _insert(
				{
					"doctype": "Cost Center",
					"cost_center_name": name,
					"company": ctx.company,
					"parent_cost_center": root,
					"is_group": 0,
					"custom_division_code": code,
				},
				log,
			).name
		)


def _group(ctx, log, name, parent, is_group=0):
	ctx.groups[name] = _get_or_create(
		"Item Group", name, {"item_group_name": name, "parent_item_group": parent, "is_group": is_group}, log
	)
	if is_group and not frappe.db.get_value("Item Group", name, "is_group"):
		frappe.db.set_value("Item Group", name, "is_group", 1)
	return ctx.groups[name]


def _make_item_groups(ctx, log):
	root = _first("Item Group", {"is_group": 1, "parent_item_group": ["in", ["", None]]}, "All Item Groups")
	cost = _group(ctx, log, "Project Cost", root, 1)
	for name in COST_GROUPS:
		_group(ctx, log, name, cost, 1 if name == "Material Cost" else 0)
	for name in ASSET_GROUPS:
		_group(ctx, log, name, ctx.groups["Material Cost"])
	services = _group(ctx, log, "Altor Services", root, 1)
	for name in SERVICE_GROUPS.values():
		_group(ctx, log, name, services)


def _item(log, code, name, group, uom, **extra):
	values = {
		"item_code": code,
		"item_name": name[:140],
		"description": name,
		"item_group": group,
		"stock_uom": _uom(uom),
		"is_stock_item": 0,
		"include_item_in_manufacturing": 0,
		**extra,
	}
	return _get_or_create("Item", code, values, log)


def _make_items(ctx, log):
	for key, items in SALES_ITEMS.items():
		for code, name, uom in items:
			_item(log, code, name, SERVICE_GROUPS[key], uom, is_sales_item=1, is_purchase_item=0)
	for code, name, group, uom, _cost, _months, _qty, _div in ASSET_ITEMS:
		fixed = {
			"is_stock_item": 0,
			"is_fixed_asset": 1,
			"asset_category": group,
			"is_grouped_asset": 1,
			"auto_create_assets": 1,
			"custom_is_project_asset": 1,
		}
		_item(log, code, name, group, uom, is_sales_item=0, is_purchase_item=1, **fixed)
		item = frappe.get_doc("Item", code)
		if any(item.get(k) != v for k, v in fixed.items()):  # an item made by an earlier version of the demo
			item.update(fixed)
			item.flags.ignore_permissions = True
			item.save()
	for _project, _supplier, period, rows in CROSS_HIRE_POS:
		for code, name, _qty, uom, _rate, _n in rows:
			_item(
				log,
				code,
				f"{name} (per {period.lower()})",
				"Cross Hire Material / Equipment Cost",
				uom,
				is_sales_item=0,
			)
	for code, name, group, uom in COST_ITEMS:
		_item(log, code, name, group, uom, is_sales_item=0)


def _make_payment_terms(ctx, log):
	for name, days in PAYMENT_TERMS.items():
		term = {
			"invoice_portion": 100,
			"due_date_based_on": "Day(s) after invoice date",
			"credit_days": days,
		}
		_get_or_create("Payment Term", name, {"payment_term_name": name, **term}, log)
		_get_or_create(
			"Payment Terms Template",
			name,
			{"template_name": name, "terms": [{"payment_term": name, **term}]},
			log,
		)


def _make_customers(ctx, log):
	group = (
		"Commercial"
		if frappe.db.exists("Customer Group", "Commercial")
		else _first("Customer Group", {"is_group": 0})
	)
	territory = (
		"United Arab Emirates"
		if frappe.db.exists("Territory", "United Arab Emirates")
		else _first("Territory", {"is_group": 0})
	)
	for c in CUSTOMERS:
		existing = frappe.db.get_value("Customer", {"customer_name": c["name"]})
		if existing:
			ctx.customers.append(existing)
			continue
		customer = _insert(
			{
				"doctype": "Customer",
				"customer_name": c["name"],
				"customer_type": "Company",
				"customer_group": group,
				"territory": territory,
				"default_currency": "AED",
				"tax_id": c["trn"],
				"payment_terms": c["terms"],
				"customer_details": f"Customer Code: {c['code']}\nTrade License: {c['license']}",
				"credit_limits": [{"company": ctx.company, "credit_limit": c["credit_limit"]}]
				if c["credit_limit"]
				else [],
			},
			log,
		)
		ctx.customers.append(customer.name)
		link = [{"link_doctype": "Customer", "link_name": customer.name}]
		first, title, email, phone = c["contact"]
		_insert(
			{
				"doctype": "Contact",
				"first_name": first,
				"designation": title,
				"company_name": c["name"],
				"is_primary_contact": 1,
				"email_ids": [{"email_id": email, "is_primary": 1}],
				"phone_nos": [{"phone": phone, "is_primary_mobile_no": 1}],
				"links": link,
			},
			log,
		)
		acc_name, acc_email = c["accounts"]
		_insert(
			{
				"doctype": "Contact",
				"first_name": acc_name,
				"designation": "Accounts",
				"company_name": c["name"],
				"email_ids": [{"email_id": acc_email, "is_primary": 1}],
				"links": link,
			},
			log,
		)
		line1, line2, city, po_box = c["address"]
		_insert(
			{
				"doctype": "Address",
				"address_title": c["name"],
				"address_type": "Billing",
				"address_line1": line1,
				"address_line2": line2,
				"city": city,
				"pincode": po_box,
				"country": "United Arab Emirates",
				"is_primary_address": 1,
				"links": link,
			},
			log,
		)


def _make_suppliers(ctx, log):
	group = _first("Supplier Group", {"is_group": 0}) or _first("Supplier Group")
	for key, name in SUPPLIERS.items():
		ctx.suppliers[key] = _get_or_create(
			"Supplier",
			name,
			{"supplier_name": name, "supplier_group": group, "supplier_type": "Company"},
			log,
			filters={"supplier_name": name},
		)


def _update_settings(ctx, log):
	settings = frappe.get_single("Altor Settings")
	for field, group in (
		("default_manpower_item_group", "Manpower Cost"),
		("outsourced_manpower_item_group", "Outsource Manpower Cost"),
	):
		if not settings.get(field) or settings.get(field).startswith(PREFIX):
			settings.set(field, ctx.groups[group])
	settings.ot_multiplier = settings.get("ot_multiplier") or 1.25
	settings.ot2_multiplier = settings.get("ot2_multiplier") or 1.5
	settings.working_hours_per_day = settings.get("working_hours_per_day") or 8
	settings.outsourced_hours_per_day = settings.get("outsourced_hours_per_day") or 10
	settings.flags.ignore_permissions = True
	settings.save()
	log.add("Altor Settings")


def _make_workers(ctx, log):
	for key, w in WORKERS.items():
		_get_or_create("Designation", w["designation"], {"designation_name": w["designation"]}, log)
		values = {k: v for k, v in w.items() if k.startswith("custom_")}
		if w.get("agency"):
			values["custom_manpower_supplier"] = ctx.suppliers[w["agency"]]
		existing = frappe.db.get_value("Employee", {"employee_name": w["first_name"], "company": ctx.company})
		if existing:
			frappe.db.set_value("Employee", existing, values)
			ctx.workers[key] = existing
			continue
		ctx.workers[key] = _insert(
			{
				"doctype": "Employee",
				"first_name": w["first_name"],
				"gender": "Male",
				"date_of_birth": "1995-05-10",
				"date_of_joining": "2024-03-01",
				"company": ctx.company,
				"status": "Active",
				"designation": w["designation"],
				**values,
			},
			log,
		).name


# ---------------------------------------------------------------------------
# Sales flow, projects, budgets
# ---------------------------------------------------------------------------


def _make_sales_flow(ctx, log, key):
	"""Lead -> Quotation -> Sales Order -> Project, numbered by division (CRM-SCF-LEAD-... -> PRJ-SCF-...)."""
	from erpnext.crm.doctype.lead.lead import make_quotation
	from erpnext.selling.doctype.quotation.quotation import make_sales_order
	from erpnext.selling.doctype.sales_order.sales_order import make_project

	p = PROJECTS[key]
	c = CUSTOMERS[p["customer"]]
	customer = ctx.customers[p["customer"]]
	t = ctx.today
	first, title, email, phone = c["contact"]
	start = add_days(t, p["start"])

	lead = frappe.get_doc(
		{
			"doctype": "Lead",
			"first_name": first,
			"job_title": title,
			"company_name": c["name"],
			"email_id": email,
			"mobile_no": phone,
			"source": "Existing Customer",
			"company": ctx.company,
			"cost_center": ctx.divisions[key],
		}
	)
	for field, value in (("custom_location", p["location"]), ("custom_scope_of_work", p["scope"])):
		if lead.meta.has_field(field):
			lead.set(field, value)
	lead = _insert(lead, log)
	# the customer already exists: link it to the lead so the Sales Order uses it
	frappe.db.set_value("Customer", customer, "lead_name", lead.name)

	q = make_quotation(lead.name)
	q.update(
		{
			"transaction_date": add_days(start, -20),
			# still valid today: ERPNext refuses a Sales Order from an expired quotation
			"valid_till": add_days(t, 15),
			"company": ctx.company,
			"cost_center": ctx.divisions[key],
			"custom_project": p["name"],
			"custom_location": p["location"],
			"custom_scope_of_work": p["scope"],
		}
	)
	q.set("items", [])
	for code, qty, rate in p["items"]:
		q.append("items", {"item_code": code, "qty": qty, "rate": rate})
	_set_taxes(q, "Sales Taxes and Charges Template", ctx)
	q = _insert(q, log, submit=True)

	so = make_sales_order(q.name)
	# the quotation's contact belongs to the Lead; the order takes the customer's own contact
	from frappe.contacts.doctype.contact.contact import get_default_contact

	so.contact_person = get_default_contact("Customer", customer)
	so.update(
		{
			"transaction_date": add_days(start, -5),
			"delivery_date": add_days(t, p["end"]),
			"po_no": p["lpo"],
			"po_date": add_days(start, -6),
		}
	)
	for row in so.items:
		row.delivery_date = so.delivery_date
	so = _insert(so, log, submit=True)
	ctx.sales_orders[key] = so.name

	project = make_project(so.name)
	project.update(
		{
			"project_name": p["name"],
			"company": ctx.company,
			"customer": customer,
			"cost_center": ctx.divisions[key],
			"quotation": q.name,
			"expected_start_date": start,
			"expected_end_date": add_days(t, p["end"]),
			"percent_complete_method": "Manual",
			"percent_complete": p["progress"],
			"status": "Open",
			"location": p["location"],
			"scope_of_work": p["scope"],
			"lpo_ref": p["lpo"],
			"lpo_date": add_days(start, -6),
		}
	)
	project = _insert(project, log)
	ctx.projects[key] = project.name
	_make_tasks(ctx, log, project, p)


def _make_tasks(ctx, log, project, p):
	t, span = ctx.today, p["end"] - p["start"]
	for subject, a, b in p["tasks"]:
		s, e = add_days(t, p["start"] + int(span * a)), add_days(t, p["start"] + int(span * b))
		progress = max(0, min(100, (p["progress"] - a * 100) / max((b - a), 0.01)))
		status = "Completed" if progress >= 100 else ("Working" if progress > 0 else "Open")
		if status != "Completed" and getdate(e) < t:
			status = "Overdue"
		_insert(
			{
				"doctype": "Task",
				"subject": subject,
				"project": project.name,
				"exp_start_date": s,
				"exp_end_date": e,
				"status": status,
				"progress": round(progress),
				"completed_on": e if status == "Completed" else None,
			},
			log,
		)


def _make_budgets(ctx, log):
	for key, project in ctx.projects.items():
		doc = frappe.get_doc(
			{
				"doctype": "Project Budget",
				"project": project,
				"cost_center": ctx.divisions[key],
				"posting_date": add_days(ctx.today, PROJECTS[key]["start"] - 3),
				"warning_threshold": 90,
				"applicable_on_material_request": 1,
				"action_if_annual_budget_exceeded_on_mr": "Warn",
				"applicable_on_purchase_order": 1,
				"action_if_annual_budget_exceeded_on_po": "Warn",
				"budget_items": [
					{"category": ctx.groups[g], "budgeted_amount": amount}
					for g, amount in PROJECTS[key]["budget"].items()
				],
			}
		)
		doc.flags.ignore_budget_warnings = True
		_insert(doc, log, submit=True)


# ---------------------------------------------------------------------------
# Project assets
# ---------------------------------------------------------------------------


def _account(ctx, log, account_type, name, like_type):
	"""Company account of a type: the demo's own if present, else created next to an existing one."""
	full = f"{name} - {ctx.abbr}"
	if frappe.db.exists("Account", full):
		return full
	sibling = frappe.db.get_value(
		"Account",
		{"company": ctx.company, "account_type": like_type, "is_group": 0},
		["parent_account", "root_type"],
		as_dict=True,
	)
	if not sibling:
		return None
	return _insert(
		{
			"doctype": "Account",
			"account_name": name,
			"company": ctx.company,
			"parent_account": sibling.parent_account,
			"account_type": account_type,
			"root_type": sibling.root_type,
		},
		log,
	).name


def _make_asset_setup(ctx, log):
	"""Location, accounts and Asset Categories for the asset list (only what is missing)."""
	ctx.location = _get_or_create("Location", "Altor Yard", {"location_name": "Altor Yard"}, log)
	fixed = _account(ctx, log, "Fixed Asset", "Scaffolding and Access Equipment", "Fixed Asset")
	acc_dep = _account(
		ctx,
		log,
		"Accumulated Depreciation",
		"Acc. Depreciation of Scaffolding and Access Equipment",
		"Accumulated Depreciation",
	)
	dep = _account(
		ctx, log, "Depreciation", "Depreciation of Scaffolding and Access Equipment", "Depreciation"
	)
	company = frappe.get_doc("Company", ctx.company)
	if not company.disposal_account:  # ERPNext needs it to scrap (write off) an asset
		company.disposal_account = frappe.db.get_value(
			"Account",
			{"company": ctx.company, "account_name": ["like", "%Fixed Assets Disposal%"], "is_group": 0},
		)
		if company.disposal_account:
			company.flags.ignore_permissions = True
			company.save()
	months = {group: m for _c, _n, group, _u, _cost, m, _q, _d in ASSET_ITEMS}
	for group, total in months.items():
		_get_or_create(
			"Asset Category",
			group,
			{
				"asset_category_name": group,
				"accounts": [
					{
						"company_name": ctx.company,
						"fixed_asset_account": fixed,
						"accumulated_depreciation_account": acc_dep,
						"depreciation_expense_account": dep,
					}
				],
				"finance_books": [
					{
						"depreciation_method": "Straight Line",
						"total_number_of_depreciations": total,
						"frequency_of_depreciation": 1,
					}
				],
			},
			log,
		)


def _make_assets(ctx, log):
	"""Opening stock as ERPNext Assets (existing assets, depreciation booked to last month end).

	Submitting each Asset creates its Project Asset (altor_project.asset_accounting.on_asset_submit).
	"""
	t = ctx.today
	start = getdate(add_days(t, -t.day + 1))  # first day of this month
	for code, name, _group, _uom, cost, months, qty, div in ASSET_ITEMS:
		existing = frappe.db.get_value("Project Asset", {"item_code": code, "remarks": ASSET_REMARK})
		if existing:  # a re-run keeps the opening stock already created
			ctx.assets[code] = existing
			continue
		used_from = getdate(add_days(t, -random.choice([120, 240, 400, 540, 700])))
		booked = min((start.year - used_from.year) * 12 + start.month - used_from.month - 1, months - 1)
		gross, salvage = qty * cost, round(qty * cost * 0.05, 2)
		asset = _insert(
			{
				"doctype": "Asset",
				"item_code": code,
				"asset_name": name[:140],
				"company": ctx.company,
				"location": ctx.location,
				"cost_center": ctx.divisions[div],
				"purchase_date": used_from,
				"available_for_use_date": used_from,
				"gross_purchase_amount": gross,
				"purchase_amount": gross,
				"asset_quantity": qty,
				"is_existing_asset": 1,
				"calculate_depreciation": 1,
				"opening_accumulated_depreciation": round((gross - salvage) / months * max(booked, 0), 2),
				"opening_number_of_booked_depreciations": max(booked, 0),
				"finance_books": [
					{
						"depreciation_method": "Straight Line",
						"total_number_of_depreciations": months,
						"frequency_of_depreciation": 1,
						"depreciation_start_date": add_days(add_days(start, 32), -add_days(start, 32).day),
						"expected_value_after_useful_life": salvage,
					}
				],
			},
			log,
			submit=True,
		)
		project_asset = frappe.db.get_value("Project Asset", {"asset": asset.name})
		if not project_asset:
			frappe.throw(f"No Project Asset was created for {asset.name}")
		frappe.db.set_value("Project Asset", project_asset, "remarks", ASSET_REMARK)
		ctx.assets[code] = project_asset
		frappe.clear_messages()


def _make_allocations(ctx, log):
	from altor_project.altor_project.doctype.asset_allocation.asset_allocation import make_asset_return

	for key, days_ago, items, returns in ALLOCATIONS:
		alloc = _insert(
			{
				"doctype": "Asset Allocation",
				"project": ctx.projects[key],
				"company": ctx.company,
				"cost_center": ctx.divisions[key],
				"delivery_date": add_days(ctx.today, -days_ago),
				"delivery_ref": f"{PREFIX}-DN-{random.randint(1000, 9999)}",
				"items": [{"project_asset": ctx.assets[code], "qty": qty} for code, qty in items],
			},
			log,
			submit=True,
		)
		for ret_days_ago, code, good, damaged in returns:
			ret = make_asset_return(alloc.name)
			ret.return_date = add_days(ctx.today, -ret_days_ago)
			ret.return_ref = f"{PREFIX}-RN-{random.randint(1000, 9999)}"
			keep = []
			for row in ret.items:
				if row.project_asset == ctx.assets[code]:
					row.returned_qty, row.damaged_qty = good, damaged
					if damaged:
						row.damage_remarks = "Bent / lost during dismantling"
					keep.append(row)
			ret.set("items", keep)
			_insert(ret, log, submit=True)


# ---------------------------------------------------------------------------
# Purchasing
# ---------------------------------------------------------------------------


def _make_cross_hire_pos(ctx, log):
	"""The client's Rental PO sheets: qty x unit rate x weeks / days."""
	for key, supplier, period, rows in CROSS_HIRE_POS:
		date = add_days(ctx.today, PROJECTS[key]["start"] + 2)
		unit = period.lower()
		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": ctx.company,
				"supplier": ctx.suppliers[supplier],
				"transaction_date": date,
				"schedule_date": add_days(date, 2),
				"cost_center": ctx.divisions[key],
				"items": [
					{
						"item_code": code,
						"qty": qty,
						"uom": _uom(uom),
						"rate": round(rate * periods, 4),
						"description": f"{name}: {qty} x AED {rate} per {unit} x {periods} {unit}s",
						"schedule_date": add_days(date, 2),
						"project": ctx.projects[key],
						"cost_center": ctx.divisions[key],
					}
					for code, name, qty, uom, rate, periods in rows
				],
			}
		)
		_set_taxes(po, "Purchase Taxes and Charges Template", ctx)
		_insert(po, log, submit=True)
		frappe.clear_messages()  # budget warnings are expected


def _purchase_invoice(ctx, log, key, supplier_key, days_ago, items, manpower=False):
	date = add_days(ctx.today, -days_ago)
	pi = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": ctx.company,
			"supplier": ctx.suppliers[supplier_key],
			"set_posting_time": 1,
			"posting_date": date,
			"bill_no": f"{PREFIX}-INV-{random.randint(10000, 99999)}",
			"bill_date": date,
			"cost_center": ctx.divisions[key],
			"items": [
				{
					"item_code": code,
					"qty": qty,
					"rate": rate,
					"project": ctx.projects[key],
					"cost_center": ctx.divisions[key],
				}
				for code, qty, rate in items
			],
		}
	)
	if manpower:
		pi.custom_is_manpower_invoice = 1
	_insert(pi, log, submit=True)


def _make_direct_invoices(ctx, log):
	for key, supplier, days_ago, items in DIRECT_INVOICES:
		_purchase_invoice(ctx, log, key, supplier, days_ago, items)


def _make_agency_invoice(ctx, log):
	"""The agency's bill for Manu: already costed on Timesheets, so left out of the budget."""
	cost = frappe.db.sql(
		"SELECT SUM(custom_total_labour_cost) FROM `tabTimesheet` WHERE docstatus = 1 AND employee = %s",
		ctx.workers["manu"],
	)[0][0]
	if flt(cost):
		_purchase_invoice(ctx, log, "scf", "agency", 0, [("SRV-MPW-OUT", 1, flt(cost, 2))], manpower=True)


# ---------------------------------------------------------------------------
# Timesheets: the client's November overtime sheet
# ---------------------------------------------------------------------------


def _make_timesheets(ctx, log):
	year, month = OT_MONTH
	# ERPNext needs an Activity Type on each row before a Timesheet can be submitted
	activity = _get_or_create("Activity Type", "Scaffolding Work", {"activity_type": "Scaffolding Work"}, log)
	for worker, employee in ctx.workers.items():
		logs = []
		for day in range(1, 31):
			hours = sheet_hours(worker, day)
			if not hours:
				continue
			normal, ot1, ot2 = hours
			total = normal + ot1 + ot2
			start = get_datetime(f"{year}-{month:02d}-{day:02d} 07:00:00")
			logs.append(
				{
					"activity_type": activity,
					"from_time": start,
					"to_time": start + timedelta(hours=total),
					"hours": total,
					"project": ctx.projects["scf"],
					"custom_ot1_hours": ot1,
					"custom_ot2_hours": ot2,
					"description": "Scaffolding erection - east facade",
				}
			)
		_insert(
			{
				"doctype": "Timesheet",
				"company": ctx.company,
				"employee": employee,
				"custom_auto_overtime": 0,  # hours split as in the sheet
				"note": f"{PREFIX} November overtime sheet",
				"time_logs": logs,
			},
			log,
			submit=True,
		)
		frappe.clear_messages()


def _post_depreciation_to_projects(ctx, log):
	"""Last month's depreciation of the issued assets -> the projects (Journal Entry)."""
	from altor_project.asset_accounting import post_depreciation_allocation

	period = str(add_days(getdate(add_days(ctx.today, -ctx.today.day + 1)), -1))[:7]
	out = post_depreciation_allocation(ctx.company, period)
	if out.get("journal_entry") and not out.get("existing"):
		log.add("Journal Entry")


def _make_sales_invoice(ctx, log):
	"""First bill of the scaffolding project: design, design review and mobilisation."""
	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

	si = make_sales_invoice(ctx.sales_orders["scf"])
	si.set("items", [r for r in si.items if r.item_code in ("SCF-SRV-001", "SCF-SRV-002", "SCF-SRV-007")])
	for row in si.items:
		if row.item_code == "SCF-SRV-007":
			row.qty = 1
	si.project = ctx.projects["scf"]
	si.remarks = f"{PREFIX} first bill"
	_insert(si, log, submit=True)


# ---------------------------------------------------------------------------
# Removal
# ---------------------------------------------------------------------------


def _delete_demo_data(store=True):
	log = DemoLog()
	like = f"{PREFIX}%"
	projects = frappe.get_all("Project", filters={"project_name": ["like", like]}, pluck="name")
	suppliers = frappe.get_all("Supplier", filters={"supplier_name": ["like", like]}, pluck="name")
	customers = frappe.get_all("Customer", filters={"customer_name": ["like", like]}, pluck="name")
	employees = frappe.get_all("Employee", filters={"employee_name": ["like", like]}, pluck="name")

	def remove(doctype, docnames):
		for name in dict.fromkeys(n for n in docnames if n):
			if not frappe.db.exists(doctype, name):
				continue
			with log.step(f"{doctype} {name}"):
				doc = frappe.get_doc(doctype, name)
				if doc.docstatus == 1:
					doc.flags.ignore_permissions = True
					doc.cancel()
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
				log.add(doctype)

	def names(doctype, filters=None, or_filters=None):
		if not frappe.db.exists("DocType", doctype):
			return []
		meta = frappe.get_meta(doctype)
		fields = list(filters or {}) + list(or_filters or {})
		if any(f not in default_fields and not meta.has_field(f) for f in fields):
			return []  # this site's version of the doctype has no such field
		return frappe.get_all(
			doctype, filters=filters, or_filters=or_filters, pluck="name", order_by="creation desc"
		)

	def parents(child, field, values):
		if not values:
			return []
		return frappe.get_all(child, filters={field: ["in", list(values)]}, pluck="parent", distinct=True)

	# the sales chain of the demo projects and of older DEMO customers / leads
	sales_orders = [s for s in (frappe.db.get_value("Project", p, "sales_order") for p in projects) if s]
	quotations = [q for q in (frappe.db.get_value("Project", p, "quotation") for p in projects) if q]
	if sales_orders:
		quotations += frappe.get_all(
			"Sales Order Item",
			filters={"parent": ["in", sales_orders], "prevdoc_docname": ["is", "set"]},
			pluck="prevdoc_docname",
			distinct=True,
		)
	if customers:
		sales_orders += names("Sales Order", {"customer": ["in", customers]})
		quotations += names("Quotation", {"party_name": ["in", customers]})
	quotations += names("Quotation", {"customer_name": ["like", like]})
	quotations = list(dict.fromkeys(quotations))
	leads = [
		q.party_name
		for q in frappe.get_all(
			"Quotation", filters={"name": ["in", quotations or [""]]}, fields=["party_name", "quotation_to"]
		)
		if q.quotation_to == "Lead"
	]
	leads += names("Lead", or_filters={"company_name": ["like", like], "lead_name": ["like", like]})
	leads = list(dict.fromkeys(leads))

	if projects:
		# month-end entries that moved asset depreciation to the demo projects
		remove(
			"Journal Entry",
			[
				j
				for j in parents("Journal Entry Account", "project", projects)
				if frappe.db.get_value("Journal Entry", j, "custom_asset_depreciation_period")
			],
		)
		remove("Timesheet", parents("Timesheet Detail", "project", projects))
		remove("Asset Return", names("Asset Return", {"project": ["in", projects]}))
		remove("Asset Allocation", names("Asset Allocation", {"project": ["in", projects]}))
		remove("Payment Certificate", names("Payment Certificate", {"project": ["in", projects]}))
		remove("Project Budget", names("Project Budget", {"project": ["in", projects]}))
		remove("Sales Invoice", parents("Sales Invoice Item", "sales_order", sales_orders))
		remove("Sales Invoice", names("Sales Invoice", {"project": ["in", projects]}))
		remove("Purchase Invoice", parents("Purchase Invoice Item", "project", projects))
		remove("Purchase Order", parents("Purchase Order Item", "project", projects))
		remove("Material Request", names("Material Request", {"custom_project": ["in", projects]}))
	if suppliers:
		remove("Purchase Invoice", names("Purchase Invoice", {"supplier": ["in", suppliers]}))
		remove("Purchase Order", names("Purchase Order", {"supplier": ["in", suppliers]}))
	if customers:
		remove("Sales Invoice", names("Sales Invoice", {"customer": ["in", customers]}))
		remove("Proforma Invoice", names("Proforma Invoice", {"customer_name": ["like", like]}))
	demo_assets = names("Project Asset", {"remarks": ["like", f"{PREFIX} %"]})
	erp_assets = [a for a in (frappe.db.get_value("Project Asset", p, "asset") for p in demo_assets) if a]
	# plus cancelled Assets of the demo items left over by an earlier run
	erp_assets += names("Asset", {"item_code": ["in", [a[0] for a in ASSET_ITEMS]], "docstatus": 2})
	remove("Project Asset", demo_assets)
	if erp_assets:  # the ERPNext Assets of the opening stock, split-off parts first
		split_off = names("Asset", {"split_from": ["in", erp_assets]})
		# entries that point at them (depreciation booked on a split / restore, write-offs) block the delete
		remove(
			"Journal Entry",
			frappe.get_all(
				"Journal Entry Account",
				filters={"reference_type": "Asset", "reference_name": ["in", split_off + erp_assets]},
				pluck="parent",
				distinct=True,
				order_by="parent desc",
			),
		)
		remove("Asset", split_off)
		remove("Asset", erp_assets)
	if employees:
		for dt in ("Timesheet", "Attendance", "Employee Checkin", "Leave Application"):
			remove(dt, names(dt, {"employee": ["in", employees]}))
	if projects:
		remove("Task", names("Task", {"project": ["in", projects]}))
		remove("Project Schedule", names("Project Schedule", {"project": ["in", projects]}))
		remove("Project", projects)
	remove("Sales Order", sales_orders)
	if quotations:
		remove("Proforma Invoice", names("Proforma Invoice", {"quotation": ["in", quotations]}))
	remove("Quotation", quotations)
	if leads:
		for customer in names("Customer", {"lead_name": ["in", leads]}):
			frappe.db.set_value("Customer", customer, "lead_name", None)
		remove("Site Visit", names("Site Visit", {"lead": ["in", leads]}))
	remove("Lead", leads)
	remove("Employee", employees)

	with log.step("Altor Settings"):
		settings = frappe.get_single("Altor Settings")
		for field in ("default_manpower_item_group", "outsourced_manpower_item_group"):
			if (settings.get(field) or "").startswith(PREFIX):
				settings.set(field, None)
		settings.flags.ignore_permissions = True
		settings.save()

	remove("Item", names("Item", {"item_code": ["like", f"{PREFIX}-%"]}))
	remove("Supplier", suppliers)
	if customers:
		remove("Contact", parents("Dynamic Link", "link_name", customers))
		remove("Address", parents("Dynamic Link", "link_name", customers))
	remove("Customer", customers)
	remove("Department", names("Department", {"department_name": ["like", like]}))
	groups = names("Item Group", {"name": ["like", like]})
	remove("Item Group", [g for g in groups if not frappe.db.get_value("Item Group", g, "is_group")])
	remove("Item Group", [g for g in groups if frappe.db.exists("Item Group", g)])
	result = log.result()
	return _store_result(result) if store else result
