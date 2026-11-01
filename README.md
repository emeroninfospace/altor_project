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

- **Project Overview** workspace: KPIs (projects, overdue, due soon, progress, open tasks), contract value,
  budget / committed / actual / balance, projects by status, budget vs utilized per project,
  item group wise budget table, budget warnings and a project list.
- **HR Dashboard** workspace: headcount, attendance today and last 7 days, leave today and pending approvals,
  department / gender / employment type / designation breakdowns, birthdays, work anniversaries,
  passports expiring and new joiners.

Both are Custom HTML Blocks (fixtures) backed by `altor_project/api/dashboard.py`.

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
