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
  Booked on the project budget's Manpower Cost line.
- **Outsourced** (no salary fields): tick Outsourced Manpower, select the Manpower Supplier / Agency and enter the
  **Hourly Charge (Agency Rate)**. Booked on the project budget's Outsource Manpower Cost line.
  cost = hourly rate x (normal hours + OT 1 x 1.25 + OT 2 x 1.5).

Submitted Timesheets with a Project count in the **Project Budget** as manpower cost, on the Item Group set in
Altor Settings (**Manpower Item Group (Own Staff)** / **(Outsourced)**), with **Own Staff Cost** and **Outsourced
Manpower Cost** shown separately. Tick **Outsourced Manpower Invoice** on the agency's Purchase Invoice so that
labour is not counted twice.

Reports: **Manpower Cost Summary** (by project, agency, employee, designation, date or item group) to check agency
bills, and **Employee Overtime** (per employee, or employee and project): days worked, normal / OT 1 / OT 2 hours,
weighted OT hours, OT rate, OT amount and total labour cost, as in the monthly overtime sheet.

### Demo data

Built from the client's ERP_Comments sheet:

```bash
bench --site <site> execute altor_project.demo.reset_demo_data   # delete + create
bench --site <site> execute altor_project.demo.make_demo_data
bench --site <site> execute altor_project.demo.delete_demo_data
```

(also whitelisted for System Managers; pass `background=1` and read the result with `altor_project.demo.demo_status`).

- **Client masters** (kept by delete_demo_data): the customers of the Customer Master sheet (TRN, contacts, address,
  payment terms, credit limit), the scaffolding division's standard quotation lines, the asset list (Project Asset
  items under the "Material Cost" budget line), the budget cost lines, the cross hire items and the workers of the
  overtime sheet (Aswin: own staff salary, Manu: outsourced hourly rate).
- **Demo transactions** (DEMO prefix, removed by delete_demo_data): a Lead -> Quotation -> Sales Order -> Project chain
  per division (Scaffolding, Cradle, Equipment Rental), project budgets (the Budget sheet figures on the scaffolding
  project), the three Rental (cross hire) POs of the sheets, opening Project Assets with sample quantities and costs,
  asset issues and a return with damaged items, Aswin's and Manu's November Timesheets exactly as in the overtime
  sheet, transport / inspection / consumables bills, the agency bill and a sales invoice.

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

Lead, Quotation, Sales Order, Project and Site Visit are numbered by division, and one enquiry keeps one number:

| Document | Default format | Example |
|---|---|---|
| Lead | `CRM-{division}-LEAD-{year}-{seq}` | CRM-SCF-LEAD-2026-0007 |
| Quotation (from that lead) | `QT-{division}-{year}-{seq}` | QT-SCF-2026-0007 |
| Sales Order (from that quotation) | `SO-{division}-{year}-{seq}` | SO-SCF-2026-0007 |
| Project (from that sales order / quotation) | `PRJ-{division}-{year}-{seq}` | PRJ-SCF-2026-0007 |
| Site Visit (from that lead; a second visit gets `-V2`) | `SV-{division}-{year}-{seq}` | SV-SCF-2026-0007 |

- `{division}` is the **Division Code** on the Cost Center (e.g. SCF, CRD). Without one, known division names map
  to SCF, CRD, EQR, RPA, CHS, MCL, TRD, MPW, otherwise the initials are used.
- Each division has its own counter per year. Documents not made from an earlier step (a direct quotation to a
  customer) take the next number. A second quotation from the same lead gets `-V2`; revisions stay `-R1`, `-R2`.
- A project made before it had a division (e.g. Altor-PR-2026-00007): set its Division, save, then **Actions >
  Use Division Number** renames it (PRJ-SCF-2026-0014); linked documents follow. A new project without a division
  takes its Sales Order's before it is numbered.
- The shared part is stored as **Division Ref No.** (SCF-2026-0007) on all four documents.
- Formats, digits and on/off: **Altor Settings > Division Numbering**. Documents without a division keep the
  standard naming series.

### Sales flow rules

- **Lead**: First Name is labelled **Company Name** (mandatory) and **Contact Name** holds the person; Middle and
  Last Name are hidden. The company also fills Organization Name, so a converted lead becomes a Company customer
  of that name, and the lead's Contact is created for the Contact Name (`events/lead.py`, `CustomLead`).
- **Quotation**: no LPO fields; the client's LPO is recorded on the Sales Order (Customer's Purchase Order) and the
  Project (LPO Ref / Date).
- **Lead > Existing Customer** (the standard customer link, relabelled and always shown): for a customer you
  already have, choose it on the Lead; Company Name and Source fill in, and the Sales Order / Sales Invoice /
  Project made from the lead's quotation is booked on that customer (no duplicate customer).
- **Quotation**: only for a Lead (`events/quotation.require_lead`, Altor Settings > Sales > Quotation Only for a
  Lead). The lead's status follows: a quotation (draft or submitted) makes it **Quotation**, deleting / cancelling
  the last one puts it back to Site Visit Completed or Open, and a submitted Sales Order makes it **Converted**.
- **Project**: only from a submitted Sales Order (Sales Order > Create > Project; Altor Settings > Sales > Project
  Only from Sales Order). It takes the order's Customer's Purchase Order No. / Date as LPO Ref / Date and the
  quotation; a corrected LPO on the submitted order updates its projects (`events/project.validate_project`).
  The Quotation has no Create > Project.
- **Sales Order**: only from a submitted Quotation (Quotation > Create > Sales Order, or Get Items From >
  Quotation). A line without a quotation is refused on save (`events/sales_order.py`); switch it off in
  **Altor Settings > Sales > Sales Order Only from Quotation**.
- **Proforma Invoice**: the **Sales Order** is mandatory (first field); the Quotation has no Create > Proforma
  Invoice / Sales Invoice any more. Select the **Sales Order** and the customer, addresses, contact, division, price list,
  items (quantity not yet on a submitted proforma), taxes and terms are filled from it. Also from the Sales Order:
  Create > Proforma Invoice. Submitted proformas of an order cannot exceed its total.

### Daily Timesheet (crew sheet)

One date, many employees: **Projects > Daily Timesheet** (also on the Altor workspace and the Project's
connections). Pick the date, project and default activity, **Add Employees** (several at once), adjust the hours
per row (a row can have its own project, task, start time and, with "Split Overtime Automatically" unticked, its
own OT 1 / OT 2). On submit each employee gets a standard ERPNext **Timesheet** for the date (rows back to back
from 08:00, or after the hours already booked that day), costed as usual (own staff / outsourced, OT, budget);
the rows show the Timesheet and its labour cost. Cancelling the Daily Timesheet cancels those Timesheets.
Timesheets keep working on their own as before.

### My Assignments (dashboard)

The **My Work** workspace (first in the sidebar) and the top of the **Altor** workspace show the logged-in
user's assigned work: every open Assign To (ToDo) on a Lead, Task, Project, Site Visit or any other document,
with who assigned it, the due date (the ToDo date, else the task / project end date), priority and the
document's status. Users change the status in place (documents with a Select status they may edit, e.g. Lead
and Task) and close the assignment with **Done**; "Done in the last 30 days" lists what they closed.
API: `altor_project/api/assignments.py`. It replaces the old Task Dashboard block (removed by a patch).
The navbar bell shows the number of unread notifications (`public/js/notification_count.js`).

### Assignment notifications

- **Assign To** on any document (Lead, Task, ...): the assignee gets a bell notification (and the notification
  email once an outgoing Email Account is set up). Frappe sends it itself; a job every minute
  (`notifications.notify_missed_assignments`) adds it for open assignments made by someone else that got none
  (seen on the live site when a lead was re-assigned back), so re-assigning a lead or assigning a task always
  notifies the new assignee within a minute.
- **Instant**: Assign To (`frappe.desk.form.assign_to.add` / `add_multiple`, replaced in hooks) writes the
  assignee's notification in the same request instead of Frappe's background job; the minute check stays as a
  safety net. Assigning something to yourself sends no notification (Frappe's rule); it still shows on My Work.
- **Lead Owner**: changing it to another user notifies the new owner.

### Project Assets (asset allocation to projects)

Scaffolding materials and equipment bought once and issued to projects. **ERPNext's Asset module keeps the
accounts** (capitalisation, monthly depreciation, split, scrap, sale); the Project Asset keeps the site side
(quantities on projects, issue / return, per-day cost to each project).

1. **Item**: tick **Project Asset** (it also ticks Is Fixed Asset, Create Grouped Asset and Auto Create Assets and
   clears Maintain Stock) and choose the **Asset Category** (accounts + depreciation method and months).
2. **Purchase Receipt (GRN)**: ERPNext creates ONE grouped **Asset** for the quantity received. Submitting that Asset
   creates the linked **Project Asset**: quantity, unit cost, salvage value and depreciation months come from the Asset
   and are read-only. Assets already owned: create them in ERPNext as existing assets (Is Existing Asset, opening
   accumulated depreciation); their Project Assets are created the same way.
3. **Asset Allocation** (issue to a project) and **Asset Return** (good and damaged / lost quantities) as before:
   the project is charged qty x (cost - salvage) / (months x 30) per unit per day while on site, and damaged / lost
   units at their book value on the return date (Project Budget, Material Cost line).
4. **Accounts for damage**: on an Asset Return the damaged / lost quantity is split off the ERPNext Asset and scrapped
   (ERPNext Split Asset + Scrap Asset: the loss goes to the company's Gain/Loss Account on Asset Disposal). Cancelling
   the return restores it (it stays a separate asset). Switch off in Altor Settings > Write Off Damaged Assets.
5. **Month end**: Project Asset Cost report > **Post Depreciation to Projects** (or Altor Settings > Post Depreciation
   to Projects Monthly) makes a Journal Entry that moves the month's depreciation of the issued assets from the
   asset's cost center to each project and its division, on the asset category's depreciation expense account, with
   the same figures as the report. One entry per company and month.

Accounting setup the client's accountant checks: Asset Categories (fixed asset, accumulated depreciation and
depreciation expense accounts, depreciation months), the Company's asset accounts (Gain/Loss Account on Asset
Disposal, Depreciation Cost Center, Asset Received But Not Billed / CWIP for GRNs) and Accounts Settings > Book
Asset Depreciation Entry Automatically.

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
