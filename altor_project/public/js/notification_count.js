// Altor: the number of unread notifications (assignments, mentions, alerts) on the navbar bell.
(function () {
	const CLS = "altor-bell-count";
	let busy = false;

	function bell() {
		return document.querySelector(".dropdown-notifications .notifications-icon") || document.querySelector(".notifications-icon");
	}

	function paint(count) {
		const el = bell();
		if (!el) return;
		let badge = el.querySelector("." + CLS);
		if (!count) {
			if (badge) badge.remove();
			return;
		}
		if (!badge) {
			badge = document.createElement("span");
			badge.className = CLS;
			el.style.position = "relative";
			el.appendChild(badge);
		}
		badge.textContent = count > 99 ? "99+" : String(count);
		badge.title = __("{0} unread notifications", [count]);
	}

	function refresh() {
		if (busy || !window.frappe || !frappe.session || !frappe.session.user || frappe.session.user === "Guest") return;
		busy = true;
		frappe
			.xcall("frappe.client.get_count", {
				doctype: "Notification Log",
				filters: { for_user: frappe.session.user, read: 0 },
			})
			.then(paint)
			.catch(() => {})
			.finally(() => (busy = false));
	}

	const style = document.createElement("style");
	style.textContent = `.${CLS}{position:absolute;top:-5px;right:-8px;min-width:17px;height:17px;padding:0 4px;border-radius:9px;
		background:var(--red-500,#e03131);color:#fff;font-size:10px;font-weight:700;line-height:17px;text-align:center;
		pointer-events:none;box-shadow:0 0 0 2px var(--navbar-bg,#fff)}`;
	document.head.appendChild(style);

	$(document).ready(() => {
		setTimeout(refresh, 1500);
		setInterval(refresh, 60000);
		if (frappe.realtime) frappe.realtime.on("notification", () => setTimeout(refresh, 500));
		// reading notifications (opening one, "Mark all as read") lowers the count
		$(document).on("click", ".dropdown-notifications .notification-item, .dropdown-notifications .mark-all-read", () => setTimeout(refresh, 1200));
		$(document).on("hidden.bs.dropdown", ".dropdown-notifications", refresh);
	});
})();
