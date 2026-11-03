### Altor Project

Altor Project

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app altor_project
```

### Dashboards & Workspaces

Four animated dashboards, each with its own workspace (shortcuts with live counts, link cards, links to the other dashboards):

- **Project Overview**: active / overdue projects, progress, open tasks, budget health (orders, manpower, direct invoices,
  remaining), own vs outsourced labour, budget used by project, and tabs for projects, item group budgets and budget warnings.
- **HR Dashboard**: headcount (own / outsourced), attendance today and last 7 days, leave, workers on site, labour cost,
  department / gender / employment type, agencies, and tabs for leave, birthdays, anniversaries, expiring passports, new joiners.
- **Stock Overview**: stock value, stock in / out, pending receipts, material issued to projects, value by item group and
  warehouse, and tabs for top items, reorder alerts, pending receipts, slow-moving stock and recent stock entries.
- **Accounts Overview**: cash & bank, receivables and payables with ageing, net profit year to date, income vs expenses
  for 6 months, this month's margin, where the money went, and tabs for overdue invoices and recent payments.

Sources live in `dashboards/` (`kit.css` / `kit.js` shared design kit plus one `.html` / `.js` per dashboard).
After editing, run `python3 dashboards/build.py` to pack them into `altor_project/fixtures/custom_html_block.json`,
then `bench --site <site> migrate`. Data comes from `altor_project/api/dashboard.py`.

### Item Group wise Project Budget

- Each **Project Budget** line is an Item Group with a Budgeted Amount (one line per Item Group).
- Figures per line: **Committed** (submitted Purchase Orders + Subcontract Work Orders), **Actual**
  (submitted Purchase Invoices + Subcontract Invoices), **Utilized** (committed + invoices not against an order),
  Balance, Utilization % and Status (Within Budget / Warning / Exceeded).
- Spend is matched through the Item Group tree, so an item in a child group counts against its parent's budget line.
- Figures update when those documents are submitted / cancelled, daily, and with **Refresh Actuals** on the form.
- **Material Request** and **Purchase Order** are checked against the budget: *Stop* blocks, *Warn* shows a warning,
  *Ignore* skips. A warning is also shown when the warning threshold (default 90%) is reached or an item group has no budget line.
- Report: **Project Budget Variance**.

### Manpower Costing (own staff and outsourced manpower)

- **Manpower Entry** (daily, per project): one row per worker: Own Staff or Outsourced (agency).
  An outsourced row can be a named worker (Employee) or a crew (agency + designation + number of workers).
  Amount = workers x (hours x hourly rate + OT hours x OT rate).
- Hourly rate comes from the Employee's **Hourly Cost Rate**, otherwise the agency rate in
  **Altor Settings > Outsourced Manpower Rates** (supplier + designation), otherwise CTC / 12 / working days / hours.
  OT rate falls back to hourly rate x OT Multiplier (default 1.25).
- Employee fields: **Outsourced Manpower**, **Manpower Supplier / Agency**, **Hourly Cost Rate**, **OT Hourly Rate**.
- Checks: own staff needs an Employee, outsourced needs an agency, no duplicate employee in an entry,
  max 24 hours per employee per day across all projects, no booking on completed / cancelled projects,
  rate required.
- The cost goes to the Project Budget line of the entry's **Budget Item Group** (Manpower Cost column) and is part of Utilized.
  Tick **Outsourced Manpower Invoice** on the agency's Purchase Invoice so that labour is not counted twice.
- **Automation** (Altor Settings > Manpower Entry Automation): every night at 01:30 one Manpower Entry per project is
  created for the previous day: named workers from Attendance (or Employee Checkins, first IN to last OUT) charged to
  the employee's **Assigned Project** (or the Project on the checkin), hours above the standard day as OT, plus each
  project's **Daily Manpower Crew** (agency, trade, workers, hours, from/to date; skipped on holidays). Already booked
  employees / crews are skipped. Entries are drafts for review unless "Submit Automatically" is ticked.
  The Manpower Entry list has a **Create from Attendance** button to run it for any past date.
- Report: **Manpower Cost Summary** (by project, agency, employee, designation, date or item group) to check agency bills.

### Demo data

```bash
bench --site <site> execute altor_project.demo.make_demo_data
bench --site <site> execute altor_project.demo.delete_demo_data
```

Creates (and removes) projects, tasks, item group budgets, purchase orders and invoices, own and outsourced
employees, manpower entries, attendance and leave requests. Every record starts with `DEMO`.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/altor_project
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
