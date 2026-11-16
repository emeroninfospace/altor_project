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

### Manpower Costing (Timesheets: normal hours, OT 1, OT 2)

Workers' hours are entered on ERPNext **Timesheets** (one per employee, a row per day / project). Each row's hours are
split into **Normal**, **OT 1** and **OT 2**:

- Normal: up to the normal hours per day (Altor Settings: **Working Hours per Day (Own Staff)** 8,
  **Normal Hours per Day (Outsourced)** 10); several rows on the same day share it.
- OT 1: hours above that on a working day (x **OT 1 Multiplier**, 1.25).
- OT 2: all hours on a holiday / weekly off of the employee's Holiday List (x **OT 2 Multiplier**, 1.5).
- Untick **Split Overtime Automatically** on the Timesheet to enter OT 1 / OT 2 by hand.

Cost (calculated on save, shown per row and as **Total Labour Cost**, also used as the Timesheet's costing amount).
Employee > **Manpower Costing**:

- **Own staff**: Basic Salary, Allowance, HRA, Transportation.
  normal hour = (Basic + Allowance + HRA + Transportation) / days in the month / 8;
  OT hour = Basic / days in the month / 8; cost = normal hours x normal hour + (OT 1 x 1.25 + OT 2 x 1.5) x OT hour.
  Without a Basic Salary the Hourly Cost Rate is used.
- **Outsourced**: tick Outsourced Manpower, select the Manpower Supplier / Agency and enter the **Hourly Cost Rate**.
  cost = hourly rate x (normal hours + OT 1 x 1.25 + OT 2 x 1.5).

Submitted Timesheets with a Project count in the **Project Budget** as manpower cost, on the Item Group set in
Altor Settings (**Manpower Item Group (Own Staff)** / **(Outsourced)**), with **Own Staff Cost** and **Outsourced
Manpower Cost** shown separately. Tick **Outsourced Manpower Invoice** on the agency's Purchase Invoice so that
labour is not counted twice.

Reports: **Manpower Cost Summary** (by project, agency, employee, designation, date or item group) to check agency
bills, and **Employee Overtime** (per employee, or employee and project): days worked, normal / OT 1 / OT 2 hours,
weighted OT hours, OT rate, OT amount and total labour cost, as in the monthly overtime sheet.

### Demo data

```bash
bench --site <site> execute altor_project.demo.make_demo_data
bench --site <site> execute altor_project.demo.delete_demo_data
```

Creates (and removes) projects, tasks, item group budgets, purchase orders and invoices, own and outsourced
employees with salary / hourly rates, timesheets, attendance and leave requests. Every record starts with `DEMO`.

### Division (Cost Center)

Divisions are Cost Centers. Every document carries its division in the `cost_center` field, labelled
**Division**: Lead and Quotation (mandatory), Sales Order, Delivery Note, Sales Invoice, Project, Project Budget,
Project Schedule, Site Visit, Proforma Invoice, Expense Entry, Material Request, Purchase Order /
Receipt / Invoice, Subcontract Work Order / Invoice, Stock Entry, Payment Entry and Expense Claim. Because the
fieldname is the same everywhere, it is carried along Lead -> Quotation -> Sales Order -> Project / Sales Invoice,
and Project -> Project Budget. Item rows take the document's division unless set otherwise.
Create one Cost Center per division under the company (e.g. Scaffolding, Equipment Rental, Cradle, Rope Access,
Construction Hoist, Mast Climber, Trading, Manpower).

#### Division numbering

Lead, Quotation, Sales Order and Project are numbered by division, and one enquiry keeps one number:

| Document | Default format | Example |
|---|---|---|
| Lead | `CRM-{division}-LEAD-{year}-{seq}` | CRM-SCF-LEAD-2026-0007 |
| Quotation (from that lead) | `QT-{division}-{year}-{seq}` | QT-SCF-2026-0007 |
| Sales Order (from that quotation) | `SO-{division}-{year}-{seq}` | SO-SCF-2026-0007 |
| Project (from that sales order / quotation) | `PRJ-{division}-{year}-{seq}` | PRJ-SCF-2026-0007 |

- `{division}` is the **Division Code** on the Cost Center (e.g. SCF, CRD). Without one, known division names map
  to SCF, CRD, EQR, RPA, CHS, MCL, TRD, MPW, otherwise the initials are used.
- Each division has its own counter per year. Documents not made from an earlier step (a direct quotation to a
  customer) take the next number. A second quotation from the same lead gets `-V2`; revisions stay `-R1`, `-R2`.
- The shared part is stored as **Division Ref No.** (SCF-2026-0007) on all four documents.
- Formats, digits and on/off: **Altor Settings > Division Numbering**. Documents without a division keep the
  standard naming series.

### Project Assets (asset allocation to projects)

Scaffolding materials and equipment that are bought once and issued to projects (Cuplock standards, ledgers,
couplers, cradles, scissor lifts, hoists ...). Office furniture and computers stay in ERPNext's own Asset module.

1. **Item**: tick **Project Asset** and enter the **Depreciation Period (Months)**.
2. **Purchase Receipt (GRN)**: on submit, every Project Asset item row becomes a **Project Asset** with the purchase
   price of the row (net, company currency) and the depreciation period (editable on the row). Existing stock is
   entered by hand as Project Assets (purchase date, quantity, unit cost, months).
3. **Project Asset** (the asset list): quantity purchased, unit cost, salvage value, depreciation months and
   - Depreciation per unit per day = (Unit Cost - Salvage Value) / (Months x 30)
   - Available / On Projects / Damaged quantities, and which projects have it now.
4. **Asset Allocation** (issue to a project): the quantity on the project is taken off the available quantity. The
   project is charged qty x rate per unit per day x days from the delivery date (both days counted, never past the end
   of the depreciation period).
5. **Asset Return** (Create > Asset Return on the allocation): returned (good) and **damaged / lost** quantities.
   Depreciation of the returned quantity stops on the return date. Damaged / lost units are written off and charged
   to the project at their book value on the return date (unit cost less depreciation since purchase, not below the
   salvage value); the charge per unit can be changed on the row.
6. **Project Budget**: depreciation and damage cost count against the budget line of the asset's Item Group
   (shown as **Asset Cost**, included in Utilized). They are refreshed after each allocation / return and every
   night, as depreciation grows each day the asset stays on site.
7. **Project Asset Cost** report: depreciation and damage cost charged to each project in any period (month end
   costing), with the quantity on site at the period end.

These figures are for project costing; no accounting (GL) entries are posted for the depreciation.

### Payment Certificate

Subcontractor's Payment Certificate, following the ALTOR template. Create it from a submitted **Subcontract Work
Order** (Create > Payment Certificate) or directly (Projects > Payment Certificate).

- Header: subcontractor, agreement (Subcontract Work Order), project, scope, budget code, client PO, application
  dates, securities / insurances / licences with validity, and the contract summary (revised contract amount =
  subcontract amount + variations + adjustments).
- Certification lines A to L are entered as **cumulative** amounts. **Previous** is taken from the last submitted
  certificate for the same agreement (or the same subcontractor and project without an agreement), and
  **This Period** = Cumulative - Previous.
- Calculated: E Gross = A+B+C+D, H Remaining Advance = F-G, O Deductions = G+I+J-K-L, P Net excl. VAT = E+F-O,
  Q = P, R VAT = Q x VAT rate (default 5%), S Net incl. VAT = P+R. A Rate % on G, I or J works the line out from
  Works Executed + Variations (advance recovery is capped at the advance paid).
- Back charges are listed with amount, VAT and total.
- Approval: Draft > Initiated > Reviewed > Checked > Authorized > Approved (or Rejected, with a reason). Each step
  records the user; Authorized and Approved need Projects Manager / Accounts Manager. Only an Approved certificate
  can be submitted. Amending a certificate increases its **Version**.
- Warnings: expired or soon to expire (30 days) securities, gross above the revised contract, recovery above the
  advance, lower cumulative than last time, duplicate application number.

### Print Formats

All Altor print formats share one design (`altor_project/templates/print/altor_print.html`) and read the company
details from the site, not from code:

- **Company**: name, logo, TRN (Tax ID), phone, email, website; **Company > Print Settings** tab: Arabic name, accent
  colour, stamp, authorised signature and signatory, footer note.
- **Address** linked to the Company, and the company **Bank Account** (Is Company Account; the default one first).

| Print format | Document |
|---|---|
| Quotation | Quotation, letter style, item wise |
| Quotation Altor | Quotation, letter style, grouped by work package (item group) |
| Proforma Invoice | Proforma Invoice (bilingual, VAT per line) |
| Altor Tax Invoice | Sales Invoice: UAE tax invoice / tax credit note (bilingual, VAT per line, bank details) |
| Altor Purchase Order | Purchase Order |
| Altor Project Budget | Project Budget (item group wise) |
| Altor Payment Certificate | Payment Certificate (subcontractor's payment certificate) |
| Altor Asset Allocation | Asset Allocation (asset issue note) |
| Altor Asset Return | Asset Return (asset return note, with damaged / lost) |

Helpers used by the templates are in `altor_project/print_utils.py` (registered as Jinja methods in `hooks.py`).

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
