frappe.ui.form.on('Task', {
 
	refresh(frm) {
		const is_supervisor    = frappe.user.has_role('Supervisor');
		const is_system_manager = frappe.user.has_role('System Manager');
		const is_admin          = frappe.session.user === 'Administrator';
        console.log('is_supervisor:', is_supervisor, 'is_system_manager:', is_system_manager, 'is_admin:', is_admin);
		if (is_supervisor && !is_system_manager && !is_admin) {
            console.log('Supervisor restrictions applied to Task form');
			lock_fields_for_supervisor(frm);
		}
	}
});
 
 
 
function lock_fields_for_supervisor(frm) {
	const allowed_fields = ['status', 'progress', 'description'];
 
	frm.fields.forEach(field => {
		const fieldname = field.df.fieldname;
		const fieldtype = field.df.fieldtype;
 
		if (['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Heading'].includes(fieldtype)) {
			return;
		}
 
		if (allowed_fields.includes(fieldname)) {
			frm.set_df_property(fieldname, 'read_only', 0);
		} else {
			frm.set_df_property(fieldname, 'read_only', 1);
		}
	});
 
	frm.refresh_fields();

	frm.$wrapper.addClass('supervisor-restricted');

	if (!document.getElementById('supervisor-assign-restrict')) {
		const style = document.createElement('style');
		style.id = 'supervisor-assign-restrict';
		style.textContent = `
			.supervisor-restricted [data-action="assign"],
			.supervisor-restricted .form-assignments .btn,
			.supervisor-restricted .form-assign-list .btn,
			.supervisor-restricted .add-assignment-btn,
			.supervisor-restricted .btn-assign-to,
			.supervisor-restricted .assigned-users .btn {
				display: none !important;
			}
			.supervisor-restricted .assigned-users .avatar-group {
				pointer-events: none !important;
			}
		`;
		document.head.appendChild(style);
	}

	function hide_assign_controls() {
		frm.$wrapper.find('[data-action="assign"], .form-assignments .btn, .form-assign-list .btn, .add-assignment-btn, .btn-assign-to').hide();
		frm.$wrapper.find('.assigned-users .avatar-group').css('pointer-events', 'none');
	}

	hide_assign_controls();
	setTimeout(hide_assign_controls, 300);
	setTimeout(hide_assign_controls, 800);

	if (frm._supervisor_observer) {
		frm._supervisor_observer.disconnect();
	}
	frm._supervisor_observer = new MutationObserver(hide_assign_controls);
	frm._supervisor_observer.observe(frm.$wrapper[0], { childList: true, subtree: true });
}