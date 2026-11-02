# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Demo (dummy) data for presentations and testing.

Everything created here starts with "DEMO" so it is easy to recognise and to remove.

    bench --site <site> execute altor_project.demo.make_demo_data
    bench --site <site> execute altor_project.demo.delete_demo_data

Both are also whitelisted for System Managers (e.g. /api/method/altor_project.demo.make_demo_data).
Every step is independent: if one fails (for example because the company has no default
payable account), it is reported and the rest still runs.
"""

import random
from contextlib import contextmanager

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, getdate, nowdate

PREFIX = "DEMO"

ITEM_GROUPS = [
	"Civil Works",
	"Electrical Works",
	"Plumbing Works",
	"HVAC Works",
	"Finishing Works",
	"Manpower",
]

# item code, name, group, rate
ITEMS = [
	("DEMO-CIV-001", "DEMO Ready Mix Concrete C40 (m3)", "Civil Works", 320),
	("DEMO-CIV-002", "DEMO Concrete Block 20cm", "Civil Works", 4.5),
	("DEMO-ELE-001", "DEMO Cable 4C x 16mm (m)", "Electrical Works", 38),
	("DEMO-ELE-002", "DEMO LED Panel Light 60x60", "Electrical Works", 95),
	("DEMO-ELE-003", "DEMO Distribution Board 24 Way", "Electrical Works", 1450),
	("DEMO-PLB-001", "DEMO PPR Pipe 32mm (m)", "Plumbing Works", 12),
	("DEMO-PLB-002", "DEMO Water Heater 80L", "Plumbing Works", 780),
	("DEMO-HVC-001", "DEMO Split AC 2 Ton", "HVAC Works", 2600),
	("DEMO-FIN-001", "DEMO Emulsion Paint 18L", "Finishing Works", 210),
	("DEMO-FIN-002", "DEMO Porcelain Tile 60x60 (m2)", "Finishing Works", 65),
	("DEMO-MPW-001", "DEMO Outsourced Manpower Service", "Manpower", 18),
]

SUPPLIERS = {
	"materials": "DEMO Emirates Building Materials LLC",
	"electrical": "DEMO Al Fajer Electrical Trading",
	"hvac": "DEMO Cool Air HVAC Contracting",
	"agency_1": "DEMO Gulf Manpower Supply Services",
	"agency_2": "DEMO Star Labour Services",
}

CUSTOMERS = ["DEMO Al Noor Real Estate", "DEMO Marina Hospitality LLC"]

DESIGNATIONS = [
	"Site Engineer",
	"Foreman",
	"Electrician",
	"Plumber",
	"Mason",
	"Carpenter",
	"Helper",
	"Accountant",
]

# agency, designation, hourly, ot hourly
AGENCY_RATES = [
	("agency_1", "", 16, 20),
	("agency_1", "Mason", 20, 25),
	("agency_1", "Electrician", 24, 30),
	("agency_1", "Helper", 14, 17.5),
	("agency_2", "", 15, 19),
	("agency_2", "Carpenter", 22, 27.5),
	("agency_2", "Helper", 13, 16),
]

# first, last, gender, designation, hourly cost (own staff) / agency (outsourced)
OWN_STAFF = [
	("Ahmed", "Khan", "Male", "Site Engineer", 85),
	("Rashid", "Ali", "Male", "Foreman", 45),
	("Suresh", "Kumar", "Male", "Electrician", 30),
	("Joseph", "Mathew", "Male", "Plumber", 28),
	("Imran", "Shaikh", "Male", "Mason", 25),
	("Fatima", "Noor", "Female", "Accountant", 60),
]
OUTSOURCED = [
	("Ramesh", "Yadav", "Male", "Mason", "agency_1"),
	("Bilal", "Hussain", "Male", "Electrician", "agency_1"),
	("Santosh", "Rai", "Male", "Helper", "agency_1"),
	("Kamal", "Hossain", "Male", "Helper", "agency_1"),
	("Arjun", "Thapa", "Male", "Carpenter", "agency_2"),
	("Nabin", "Gurung", "Male", "Helper", "agency_2"),
	("Ravi", "Shetty", "Male", "Carpenter", "agency_2"),
	("Mohan", "Das", "Male", "Helper", "agency_2"),
]

# key, name, status, start offset, end offset, progress, customer index, contract
PROJECTS = [
	("villa", "DEMO Villa Renovation - Jumeirah", "Open", -95, -5, 72, 0, 640000),
	("office", "DEMO Office Fit-out - Business Bay", "Open", -50, 20, 41, 1, 480000),
	("warehouse", "DEMO Warehouse MEP - Al Quoz", "Open", -21, 140, 14, 0, 910000),
	("shop", "DEMO Retail Shop Interior - Deira", "Completed", -200, -60, 100, 1, 150000),
]

# budget per project and item group. The villa is set up to go over budget on
# electrical works and close to the limit on civil works.
BUDGETS = {
	"villa": {
		"Civil Works": 60000,
		"Electrical Works": 25000,
		"Plumbing Works": 30000,
		"Finishing Works": 45000,
		"Manpower": 70000,
	},
	"office": {"Electrical Works": 60000, "HVAC Works": 70000, "Finishing Works": 55000, "Manpower": 60000},
	"warehouse": {
		"Electrical Works": 150000,
		"Plumbing Works": 80000,
		"HVAC Works": 160000,
		"Manpower": 120000,
	},
}

# project, supplier key, days ago, [(item, qty)], invoice: None / "full"
PURCHASE_ORDERS = [
	("villa", "materials", 80, [("DEMO-CIV-001", 120), ("DEMO-CIV-002", 2000)], "full"),
	("villa", "electrical", 60, [("DEMO-ELE-001", 400), ("DEMO-ELE-003", 4)], "full"),
	("villa", "electrical", 20, [("DEMO-ELE-002", 60)], None),
	("villa", "materials", 30, [("DEMO-PLB-001", 600), ("DEMO-PLB-002", 6)], "full"),
	("villa", "materials", 10, [("DEMO-FIN-001", 40), ("DEMO-FIN-002", 300)], None),
	("office", "electrical", 40, [("DEMO-ELE-001", 300), ("DEMO-ELE-002", 120)], "full"),
	("office", "hvac", 35, [("DEMO-HVC-001", 12)], None),
	("office", "materials", 15, [("DEMO-FIN-002", 250)], None),
	("warehouse", "electrical", 18, [("DEMO-ELE-001", 900), ("DEMO-ELE-003", 10)], None),
	("warehouse", "hvac", 12, [("DEMO-HVC-001", 20)], None),
	("warehouse", "materials", 8, [("DEMO-PLB-001", 1500)], None),
]

# Direct invoices (no purchase order): project, supplier key, days ago, items
DIRECT_INVOICES = [
	("office", "materials", 25, [("DEMO-FIN-001", 30)]),
	("villa", "materials", 6, [("DEMO-CIV-002", 900)]),
]


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
	meta = frappe.get_meta(doc.doctype)
	df = meta.get_field("naming_series")
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


@frappe.whitelist()
def make_demo_data(company=None, background=0):
	"""Create demo masters and transactions. Returns what was created and any step that failed."""
	frappe.only_for("System Manager")
	if cint(background):
		frappe.enqueue("altor_project.demo._make_demo_data", queue="long", timeout=1800, company=company)
		return {"queued": True}
	return _make_demo_data(company)


def _make_demo_data(company=None):
	random.seed(42)
	log = DemoLog()
	today = getdate(nowdate())
	company = company or frappe.defaults.get_global_default("company") or _first("Company")
	if not company:
		frappe.throw("Create a Company first.")

	if frappe.db.exists("Project", {"project_name": PROJECTS[0][1]}):
		return {
			"message": "Demo data already exists. Run delete_demo_data first to recreate it.",
			**log.result(),
		}

	abbr = frappe.get_cached_value("Company", company, "abbr")
	# Budget figures are recalculated once at the end instead of after every document
	frappe.flags.altor_skip_budget_update = True
	ctx = frappe._dict(
		company=company,
		abbr=abbr,
		today=today,
		groups={},
		suppliers={},
		customers=[],
		employees={},
		projects={},
		department=None,
	)

	with log.step("Masters"):
		_make_masters(ctx, log)
	with log.step("Altor Settings"):
		_update_settings(ctx, log)
	with log.step("Employees"):
		_make_employees(ctx, log)
	with log.step("Projects and tasks"):
		_make_projects(ctx, log)
	with log.step("Project budgets"):
		_make_budgets(ctx, log)
	for i, po in enumerate(PURCHASE_ORDERS):
		with log.step(f"Purchase Order {i + 1}"):
			_make_purchase_order(ctx, log, *po)
	for i, inv in enumerate(DIRECT_INVOICES):
		with log.step(f"Direct Purchase Invoice {i + 1}"):
			_make_direct_invoice(ctx, log, *inv)
	with log.step("Manpower entries"):
		_make_manpower_entries(ctx, log)
	with log.step("Agency invoice"):
		_make_agency_invoice(ctx, log)
	with log.step("Attendance"):
		_make_attendance(ctx, log)
	with log.step("Employee checkins"):
		_make_checkins(ctx, log)
	with log.step("Leave applications"):
		_make_leave_applications(ctx, log)
	frappe.flags.altor_skip_budget_update = False
	with log.step("Budget figures"):
		from altor_project.budget import update_project_budget

		for project in ctx.projects.values():
			update_project_budget(project)

	return log.result()


# ---------------------------------------------------------------------------
# Masters
# ---------------------------------------------------------------------------


def _make_masters(ctx, log):
	root_group = _first(
		"Item Group", {"is_group": 1, "parent_item_group": ["in", ["", None]]}, "All Item Groups"
	)
	parent = _get_or_create(
		"Item Group",
		f"{PREFIX} Construction",
		{"item_group_name": f"{PREFIX} Construction", "is_group": 1, "parent_item_group": root_group},
		log,
	)
	for g in ITEM_GROUPS:
		name = f"{PREFIX} {g}"
		ctx.groups[g] = _get_or_create(
			"Item Group", name, {"item_group_name": name, "parent_item_group": parent}, log
		)

	uom = "Nos" if frappe.db.exists("UOM", "Nos") else _first("UOM")
	for code, item_name, group, rate in ITEMS:
		_get_or_create(
			"Item",
			code,
			{
				"item_code": code,
				"item_name": item_name,
				"item_group": ctx.groups[group],
				"stock_uom": uom,
				"is_stock_item": 0,
				"is_purchase_item": 1,
				"is_sales_item": 1,
				"include_item_in_manufacturing": 0,
				"standard_rate": rate,
				"valuation_rate": rate,
				"description": item_name,
			},
			log,
		)

	supplier_group = _first("Supplier Group", {"is_group": 0}) or _first("Supplier Group")
	for key, name in SUPPLIERS.items():
		ctx.suppliers[key] = _get_or_create(
			"Supplier",
			name,
			{"supplier_name": name, "supplier_group": supplier_group, "supplier_type": "Company"},
			log,
			filters={"supplier_name": name},
		)

	customer_group = _first("Customer Group", {"is_group": 0}) or _first("Customer Group")
	territory = _first("Territory", {"is_group": 0}) or _first("Territory")
	for name in CUSTOMERS:
		ctx.customers.append(
			_get_or_create(
				"Customer",
				name,
				{
					"customer_name": name,
					"customer_type": "Company",
					"customer_group": customer_group,
					"territory": territory,
				},
				log,
				filters={"customer_name": name},
			)
		)

	for d in DESIGNATIONS:
		_get_or_create("Designation", d, {"designation_name": d}, log)

	dept_name = f"{PREFIX} Site Operations"
	parent_dept = _first("Department", {"is_group": 1}) or "All Departments"
	ctx.department = _get_or_create(
		"Department",
		f"{dept_name} - {ctx.abbr}",
		{"department_name": dept_name, "company": ctx.company, "parent_department": parent_dept},
		log,
		filters={"department_name": dept_name, "company": ctx.company},
	)


def _update_settings(ctx, log):
	settings = frappe.get_single("Altor Settings")
	if not settings.get("default_manpower_item_group"):
		settings.default_manpower_item_group = ctx.groups["Manpower"]
	settings.ot_multiplier = settings.get("ot_multiplier") or 1.25
	settings.working_days_per_month = settings.get("working_days_per_month") or 26
	settings.working_hours_per_day = settings.get("working_hours_per_day") or 8
	existing = {(r.supplier, r.designation or "") for r in settings.get("manpower_rates") or []}
	for agency, designation, hourly, ot in AGENCY_RATES:
		key = (ctx.suppliers[agency], designation)
		if key not in existing:
			settings.append(
				"manpower_rates",
				{
					"supplier": key[0],
					"designation": designation or None,
					"hourly_rate": hourly,
					"ot_hourly_rate": ot,
				},
			)
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.local.altor_manpower_settings = None  # reset cached rates
	log.add("Altor Settings")


def _employee(ctx, log, first, last, gender, designation, joined_days_ago, extra):
	full = f"{PREFIX} {first} {last}"
	existing = frappe.db.get_value("Employee", {"employee_name": full, "company": ctx.company}, "name")
	if existing:
		return existing
	t = ctx.today
	# Spread birthdays / anniversaries / passport expiry so the HR dashboard has something to show
	dob = getdate(add_days(t, random.randint(-10, 40)))
	try:
		dob = dob.replace(year=t.year - random.randint(24, 48))
	except ValueError:  # 29 Feb
		dob = dob.replace(day=28, year=t.year - 30)
	doj = add_days(t, -joined_days_ago)
	values = {
		"doctype": "Employee",
		"first_name": f"{PREFIX} {first}",
		"last_name": last,
		"gender": gender,
		"date_of_birth": dob,
		"date_of_joining": doj,
		"company": ctx.company,
		"status": "Active",
		"designation": designation,
		"department": ctx.department,
		**extra,
	}
	meta = frappe.get_meta("Employee")
	if meta.has_field("valid_upto"):
		values["passport_number"] = f"P{random.randint(1000000, 9999999)}"
		values["valid_upto"] = add_days(t, random.choice([-12, 25, 45, 200, 400, 700]))
	if meta.has_field("employment_type") and frappe.db.exists("Employment Type", "Full-time"):
		values["employment_type"] = (
			"Full-time"
			if not extra.get("custom_is_outsourced")
			else ("Contract" if frappe.db.exists("Employment Type", "Contract") else "Full-time")
		)
	return _insert(values, log).name


def _make_employees(ctx, log):
	for i, (first, last, gender, designation, hourly) in enumerate(OWN_STAFF):
		ctx.employees.setdefault("own", []).append(
			_employee(
				ctx,
				log,
				first,
				last,
				gender,
				designation,
				random.choice([365 * 2 - 20, 400, 365 * 3 - 5, 900, 30, 365 + 10]) if i else 365 * 4 - 8,
				{"custom_hourly_cost_rate": hourly, "custom_ot_hourly_rate": round(hourly * 1.25, 2)},
			)
		)
	for first, last, gender, designation, agency in OUTSOURCED:
		ctx.employees.setdefault("outsourced", []).append(
			_employee(
				ctx,
				log,
				first,
				last,
				gender,
				designation,
				random.randint(10, 500),
				{"custom_is_outsourced": 1, "custom_manpower_supplier": ctx.suppliers[agency]},
			)
		)


# ---------------------------------------------------------------------------
# Projects, tasks, budgets
# ---------------------------------------------------------------------------


def _make_projects(ctx, log):
	t = ctx.today
	for key, name, status, start, end, progress, cust, contract in PROJECTS:
		doc = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": name,
				"company": ctx.company,
				"customer": ctx.customers[cust],
				"expected_start_date": add_days(t, start),
				"expected_end_date": add_days(t, end),
				"percent_complete_method": "Manual",
				"percent_complete": progress,
				"estimated_costing": contract * 0.78,
				"status": "Open",
				"location": name.split(" - ")[-1],
				"scope_of_work": name.replace(f"{PREFIX} ", ""),
			}
		)
		_insert(doc, log)
		ctx.projects[key] = doc.name
		_make_tasks(ctx, log, doc, start, end, progress)
		if status != "Open":
			frappe.db.set_value("Project", doc.name, "status", status)


def _make_tasks(ctx, log, project, start, end, progress):
	t = ctx.today
	span = end - start
	phases = [
		("Mobilisation & Site Setup", 0.0, 0.1),
		("Civil & Structural", 0.1, 0.45),
		("MEP Installation", 0.35, 0.8),
		("Finishing & Handover", 0.75, 1.0),
	]
	for subject, a, b in phases:
		s, e = add_days(t, start + int(span * a)), add_days(t, start + int(span * b))
		phase_progress = max(0, min(100, (progress - a * 100) / max((b - a), 0.01)))
		status = "Completed" if phase_progress >= 100 else ("Working" if phase_progress > 0 else "Open")
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
				"progress": round(phase_progress),
				"completed_on": e if status == "Completed" else None,
				"priority": random.choice(["Low", "Medium", "High"]),
			},
			log,
		)


def _make_budgets(ctx, log):
	for key, lines in BUDGETS.items():
		doc = frappe.get_doc(
			{
				"doctype": "Project Budget",
				"project": ctx.projects[key],
				"posting_date": add_days(ctx.today, -90),
				"warning_threshold": 90,
				"applicable_on_material_request": 1,
				"action_if_annual_budget_exceeded_on_mr": "Warn",
				"applicable_on_purchase_order": 1,
				"action_if_annual_budget_exceeded_on_po": "Warn",
				"budget_items": [
					{"category": ctx.groups[g], "budgeted_amount": amt, "boq_amount": round(amt * 1.22)}
					for g, amt in lines.items()
				],
			}
		)
		doc.flags.ignore_budget_warnings = True
		_insert(doc, log, submit=True)


# ---------------------------------------------------------------------------
# Purchasing
# ---------------------------------------------------------------------------


def _rate(item_code):
	return next(r for c, _n, _g, r in ITEMS if c == item_code)


def _make_purchase_order(ctx, log, project_key, supplier_key, days_ago, items, invoice):
	date = add_days(ctx.today, -days_ago)
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": ctx.company,
			"supplier": ctx.suppliers[supplier_key],
			"transaction_date": date,
			"schedule_date": add_days(date, 7),
			"items": [
				{
					"item_code": code,
					"qty": qty,
					"rate": _rate(code),
					"schedule_date": add_days(date, 7),
					"project": ctx.projects[project_key],
				}
				for code, qty in items
			],
		}
	)
	_insert(po, log, submit=True)
	frappe.clear_messages()  # budget warnings are expected here
	if invoice:
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		pi = make_purchase_invoice(po.name)
		pi.set_posting_time = 1
		pi.posting_date = add_days(date, 10) if add_days(date, 10) <= ctx.today else ctx.today
		pi.bill_no = f"{PREFIX}-{po.name}"
		pi.bill_date = pi.posting_date
		_insert(pi, log, submit=True)


def _make_direct_invoice(ctx, log, project_key, supplier_key, days_ago, items, manpower=False):
	date = add_days(ctx.today, -days_ago)
	pi = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": ctx.company,
			"supplier": ctx.suppliers[supplier_key],
			"set_posting_time": 1,
			"posting_date": date,
			"bill_no": f"{PREFIX}-INV-{random.randint(1000, 9999)}",
			"bill_date": date,
			"items": [
				{"item_code": code, "qty": qty, "rate": _rate(code), "project": ctx.projects[project_key]}
				for code, qty in items
			],
		}
	)
	if manpower:
		pi.custom_is_manpower_invoice = 1
	_insert(pi, log, submit=True)


def _make_agency_invoice(ctx, log):
	"""An agency bill for labour already booked in Manpower Entries (left out of the budget)."""
	hours = frappe.db.sql(
		"""SELECT SUM(d.no_of_workers * (IFNULL(d.working_hours, 0) + IFNULL(d.ot_hours, 0)))
		FROM `tabManpower Entry Detail` d INNER JOIN `tabManpower Entry` me ON me.name = d.parent
		WHERE me.docstatus = 1 AND me.project = %s AND d.supplier = %s""",
		(ctx.projects["villa"], ctx.suppliers["agency_1"]),
	)[0][0]
	if flt(hours):
		_make_direct_invoice(ctx, log, "villa", "agency_1", 1, [("DEMO-MPW-001", flt(hours))], manpower=True)


# ---------------------------------------------------------------------------
# Manpower, attendance, leave
# ---------------------------------------------------------------------------


def _make_manpower_entries(ctx, log):
	own, out = ctx.employees.get("own", []), ctx.employees.get("outsourced", [])
	# Fixed crews per project so nobody is booked twice on the same day
	crews = {
		"villa": {"own": own[1:3], "out": out[0:3], "crew": (ctx.suppliers["agency_1"], "Helper", 4)},
		"office": {"own": own[3:5], "out": out[4:6], "crew": (ctx.suppliers["agency_2"], "Helper", 3)},
		"warehouse": {
			"own": own[0:1],
			"out": out[6:8] + out[3:4],
			"crew": (ctx.suppliers["agency_2"], "Carpenter", 2),
		},
	}
	group = ctx.groups["Manpower"]
	for key, crew in crews.items():
		start = max(-26, PROJECTS[[p[0] for p in PROJECTS].index(key)][3])
		for offset in range(start, 1):
			day = add_days(ctx.today, offset)
			if getdate(day).weekday() == 6 or random.random() < 0.25:  # Sundays off, and not every day booked
				continue
			details = []
			for emp in crew["own"]:
				details.append(
					{
						"worker_type": "Own Staff",
						"employee": emp,
						"working_hours": 8,
						"ot_hours": random.choice([0, 0, 1, 2]),
					}
				)
			for emp in crew["out"]:
				if random.random() < 0.9:
					details.append(
						{
							"worker_type": "Outsourced",
							"employee": emp,
							"working_hours": 8,
							"ot_hours": random.choice([0, 1, 2, 3]),
						}
					)
			supplier, designation, n = crew["crew"]
			details.append(
				{
					"worker_type": "Outsourced",
					"supplier": supplier,
					"designation": designation,
					"no_of_workers": n + random.randint(-1, 2),
					"working_hours": 8,
					"ot_hours": random.choice([0, 2]),
				}
			)
			_insert(
				{
					"doctype": "Manpower Entry",
					"project": ctx.projects[key],
					"posting_date": day,
					"item_group": group,
					"details": details,
				},
				log,
				submit=True,
			)
			frappe.clear_messages()


def _make_attendance(ctx, log):
	if not frappe.db.exists("DocType", "Attendance"):
		return
	employees = ctx.employees.get("own", []) + ctx.employees.get("outsourced", [])
	for offset in range(-6, 1):
		day = add_days(ctx.today, offset)
		if getdate(day).weekday() == 6:
			continue
		for emp in employees:
			status = random.choices(["Present", "Absent", "Half Day", "Work From Home"], [86, 6, 5, 3])[0]
			try:
				_insert(
					{
						"doctype": "Attendance",
						"employee": emp,
						"attendance_date": day,
						"status": status,
						"company": ctx.company,
					},
					log,
					submit=True,
				)
			except Exception:
				frappe.clear_messages()  # holiday or already marked: skip this one


def _make_checkins(ctx, log):
	if not frappe.db.exists("DocType", "Employee Checkin"):
		return
	for emp in (ctx.employees.get("own", []) + ctx.employees.get("outsourced", []))[:10]:
		time = get_datetime(f"{ctx.today} 07:{random.randint(10, 55):02d}:00")
		try:
			_insert({"doctype": "Employee Checkin", "employee": emp, "log_type": "IN", "time": time}, log)
		except Exception:
			frappe.clear_messages()


def _make_leave_applications(ctx, log):
	if not frappe.db.exists("DocType", "Leave Application"):
		return
	leave_type = frappe.db.get_value("Leave Type", {"is_lwp": 1}, "name") or _first("Leave Type")
	if not leave_type:
		return
	own = ctx.employees.get("own", [])
	for emp, start, days in ((own[2], 3, 2), (own[5], 10, 4)) if len(own) > 5 else ():
		try:
			_insert(
				{
					"doctype": "Leave Application",
					"employee": emp,
					"leave_type": leave_type,
					"from_date": add_days(ctx.today, start),
					"to_date": add_days(ctx.today, start + days - 1),
					"status": "Open",
					"description": "DEMO leave request",
					"company": ctx.company,
				},
				log,
			)
		except Exception:
			frappe.clear_messages()


# ---------------------------------------------------------------------------
# Removal
# ---------------------------------------------------------------------------


@frappe.whitelist()
def delete_demo_data():
	"""Cancel and delete everything make_demo_data created (names starting with DEMO)."""
	frappe.only_for("System Manager")
	log = DemoLog()
	like = f"{PREFIX} %"
	projects = frappe.get_all("Project", filters={"project_name": ["like", like]}, pluck="name")
	suppliers = frappe.get_all("Supplier", filters={"supplier_name": ["like", like]}, pluck="name")
	employees = frappe.get_all("Employee", filters={"employee_name": ["like", like]}, pluck="name")

	def remove(doctype, names):
		for name in names:
			with log.step(f"{doctype} {name}"):
				doc = frappe.get_doc(doctype, name)
				if doc.docstatus == 1:
					doc.flags.ignore_permissions = True
					doc.cancel()
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
				log.add(doctype)

	def names(doctype, filters):
		return frappe.get_all(doctype, filters=filters, pluck="name", order_by="creation desc")

	if projects:
		remove("Manpower Entry", names("Manpower Entry", {"project": ["in", projects]}))
	if suppliers:
		remove("Purchase Invoice", names("Purchase Invoice", {"supplier": ["in", suppliers]}))
		remove("Purchase Order", names("Purchase Order", {"supplier": ["in", suppliers]}))
	if projects:
		remove("Project Budget", names("Project Budget", {"project": ["in", projects]}))
	if employees:
		for dt in ("Attendance", "Employee Checkin", "Leave Application"):
			if frappe.db.exists("DocType", dt):
				remove(dt, names(dt, {"employee": ["in", employees]}))
	if projects:
		remove("Task", names("Task", {"project": ["in", projects]}))
		remove("Project", projects)
	remove("Employee", employees)

	with log.step("Altor Settings rates"):
		settings = frappe.get_single("Altor Settings")
		keep = [r for r in settings.get("manpower_rates") or [] if r.supplier not in suppliers]
		if len(keep) != len(settings.get("manpower_rates") or []):
			settings.set("manpower_rates", keep)
		if (settings.get("default_manpower_item_group") or "").startswith(PREFIX):
			settings.default_manpower_item_group = None
		settings.flags.ignore_permissions = True
		settings.save()

	remove("Item", names("Item", {"item_code": ["like", f"{PREFIX}-%"]}))
	remove("Supplier", suppliers)
	remove("Customer", names("Customer", {"customer_name": ["like", like]}))
	remove("Department", names("Department", {"department_name": ["like", like]}))
	remove(
		"Item Group",
		[g for g in names("Item Group", {"name": ["like", like]}) if g != f"{PREFIX} Construction"],
	)
	remove("Item Group", names("Item Group", {"name": f"{PREFIX} Construction"}))
	return log.result()
