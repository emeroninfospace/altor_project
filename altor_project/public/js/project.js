// Copyright (c) 2025, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project', {
	refresh(frm) {
		const is_supervisor     = frappe.user.has_role('Supervisor');
		const is_system_manager = frappe.user.has_role('System Manager');
		const is_admin          = frappe.session.user === 'Administrator';
		const is_restricted     = is_supervisor && !is_system_manager && !is_admin;

		// a project is made from a submitted Sales Order (Altor Settings > Project Only from Sales Order)
		if (frm.is_new() && !frm.doc.sales_order && !is_restricted) {
			frm.set_intro(
				__('Make projects from a submitted Sales Order: Sales Order > Create > Project. The customer LPO comes from the order.'),
				'orange'
			);
		}

		if (is_restricted) {
			if (frm.is_new()) {
				frm.set_intro(
					__('Supervisors are not allowed to create new Projects.'),
					'red'
				);
				frm.disable_save();
			}

			frm.fields.forEach(field => {
				const fieldtype = field.df.fieldtype;
				if (['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Heading'].includes(fieldtype)) {
					return;
				}
				frm.set_df_property(field.df.fieldname, 'read_only', 1);
			});

			frm.refresh_fields();

			setTimeout(() => {
				frm.remove_custom_button('Duplicate Project with Tasks', 'Actions');
				frm.remove_custom_button('Update Costing and Billing', 'Actions');
				frm.remove_custom_button('Set Project Status', 'Actions');
			}, 100);
		}

		setTimeout(() => {
			frm.remove_custom_button('Gantt Chart', 'View');
		}, 10);

		if (!frm.is_new()) {

			if (!is_restricted) {
				frm.add_custom_button(__('Project Schedule'), () => {
					frappe.call({
						method:   'altor_project.events.project.create_project_schedule',
						args:     { project: frm.doc.name },
						callback(r) {
							if (r.message) frappe.set_route('Form', 'Project Schedule', r.message);
						}
					});
				}, __('Create'));

				frm.add_custom_button(__('Project Budget'), () => {
					frappe.call({
						method:   'altor_project.events.project.make_project_budget',
						args:     { project: frm.doc.name },
						callback(r) {
							if (r.message) frappe.set_route('Form', 'Project Budget', r.message);
						}
					});
				}, __('Create'));

				// any project: lines still to request from its Sales Order / Quotation, else an empty request
				frm.add_custom_button(__('Material Request'), () => {
					frappe.model.open_mapped_doc({
						method: 'altor_project.events.project.create_material_request',
						frm: frm,
					});
				}, __('Create'));

				frm.add_custom_button(__('Subcontract Work Order'), () => {
					create_subcontracting_order(frm);
				}, __('Create'));

				frm.add_custom_button(__('Gantt View'), () => {
					frappe.route_options = { project: frm.doc.name };
					frappe.set_route('List', 'Project', 'Gantt');
				}, __('View'));
			}

			// a project made before it had a division (e.g. Altor-PR-2026-00007): rename it to PRJ-<division>-...
			if (!is_restricted && !frm.doc.custom_division_ref && frm.perm[0] && frm.perm[0].write) {
				frm.add_custom_button(__('Use Division Number'), () => {
					if (!frm.doc.cost_center) {
						frappe.msgprint(__('Set the Division on this project and save it first.'));
						return;
					}
					frappe.confirm(
						__('Rename {0} to its division number? Tasks, timesheets, budgets and other linked documents follow.', [`<b>${frappe.utils.escape_html(frm.doc.name)}</b>`]),
						() => frappe.call({
							method: 'altor_project.custom_and_property_setter.division_naming.use_division_number',
							args: { doctype: 'Project', name: frm.doc.name },
							freeze: true,
							callback(r) {
								if (r.message) frappe.set_route('Form', 'Project', r.message);
							},
						})
					);
				}, __('Actions'));
			}

			const btn = frm.add_custom_button(__('Project Report'), () => {
				frappe.set_route('query-report', 'Project Wise', {
					project: frm.doc.name
				});
			}, __('View'));
			$(btn).addClass('btn-primary');
		}

		if (!is_restricted && frm.is_new()) {
			frm.add_custom_button(__('Subcontract Work Order'), () => {
				create_subcontracting_order(frm);
			}, __('Create'));
		}
	}
});


function create_subcontracting_order(frm) {
	frappe.new_doc('Subcontract Work Order', {
		project:          frm.doc.name,
		company:          frm.doc.company || frappe.defaults.get_default('company'),
		transaction_date: frappe.datetime.nowdate(),
		cost_center:      frm.doc.cost_center
	});
}

function create_subcontracting_receipt(frm) {
	frappe.new_doc('Subcontracting Receipt', {
		project:      frm.doc.name,
		company:      frm.doc.company || frappe.defaults.get_default('company'),
		posting_date: frappe.datetime.nowdate()
	});
}