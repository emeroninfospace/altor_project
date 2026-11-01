// Copyright (c) 2025, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project', {
	refresh(frm) {
		const is_supervisor     = frappe.user.has_role('Supervisor');
		const is_system_manager = frappe.user.has_role('System Manager');
		const is_admin          = frappe.session.user === 'Administrator';
		const is_restricted     = is_supervisor && !is_system_manager && !is_admin;

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

				if (frm.doc.custom_boq_items) {
					frm.add_custom_button(__('Material Request'), () => {
						frappe.call({
							method:   'altor_project.events.project.create_material_request',
							args:     { name: frm.doc.name },
							callback(r) {
								if (r.message) frappe.set_route('Form', 'Material Request', r.message);
							}
						});
					}, __('Create'));
				}

				frm.add_custom_button(__('Subcontract Work Order'), () => {
					create_subcontracting_order(frm);
				}, __('Create'));

				frm.add_custom_button(__('Gantt View'), () => {
					frappe.route_options = { project: frm.doc.name };
					frappe.set_route('List', 'Project', 'Gantt');
				}, __('View'));
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
		bill_of_quantity: frm.doc.custom_bill_of_quantity
	});
}

function create_subcontracting_receipt(frm) {
	frappe.new_doc('Subcontracting Receipt', {
		project:      frm.doc.name,
		company:      frm.doc.company || frappe.defaults.get_default('company'),
		posting_date: frappe.datetime.nowdate()
	});
}