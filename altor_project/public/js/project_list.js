frappe.listview_settings['Project'] = {
 
	onload(listview) {
		const is_supervisor     = frappe.user.has_role('Supervisor');
		const is_system_manager = frappe.user.has_role('System Manager');
		const is_admin          = frappe.session.user === 'Administrator';
 
		if (is_supervisor && !is_system_manager && !is_admin) {
			listview.page.btn_primary.hide();
 
			listview.page.add_actions_btn && listview.page.add_actions_btn.hide();
		}
	}
};