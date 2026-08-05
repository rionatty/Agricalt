// Agriculture Dashboard — Helpdesk-style landing page (UI structure focus)
// Renders a welcome banner, KPI stat cards, a Recent Activity panel and an
// analytics section. Self-contained: styles are inlined and scoped to .agri-dash.

frappe.pages["agriculture-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Agriculture"),
		single_column: true,
	});

	const $main = $(wrapper).find(".layout-main-section");
	$main.addClass("agri-dash-host").empty().html(render());

	fill_metrics();
	fill_recent();
	render_charts();
};

frappe.pages["agriculture-dashboard"].on_page_show = function () {
	// Re-draw charts when navigating back so canvases size correctly
	if (window.__agri_render_charts) window.__agri_render_charts();
};

function greeting() {
	const h = new Date().getHours();
	if (h < 12) return __("Good morning");
	if (h < 17) return __("Good afternoon");
	return __("Good evening");
}

function render() {
	const name = frappe.session.user_fullname || frappe.session.user || "there";
	const dateLabel = new Date().toLocaleDateString(undefined, {
		weekday: "long", month: "short", day: "numeric",
	});

	return `
<style>
.agri-dash { --c-blue:#2f7df6; --c-green:#22a06b; --c-teal:#13b4b1; --c-orange:#f6a609;
	--c-pink:#ec4a7d; --c-purple:#8b5cf6; --card-radius:16px;
	font-family:inherit; color:#1f2933; padding-bottom:40px; }

/* Welcome banner */
.agri-banner { display:flex; align-items:center; justify-content:space-between; gap:16px;
	background:linear-gradient(120deg,#0f3d2e 0%,#1b5e20 45%,#2e7d32 100%);
	border-radius:20px; padding:22px 26px; color:#fff;
	box-shadow:0 10px 30px rgba(15,61,46,.30); margin-bottom:22px; }
.agri-banner-left { display:flex; align-items:center; gap:16px; }
.agri-avatar { width:46px; height:46px; border-radius:50%; background:rgba(255,255,255,.18);
	display:flex; align-items:center; justify-content:center; font-weight:700; font-size:18px;
	border:1px solid rgba(255,255,255,.3); }
.agri-greeting { font-size:22px; font-weight:700; line-height:1.2; }
.agri-subtle { font-size:13px; opacity:.8; margin-top:2px; }
.agri-banner-right { display:flex; align-items:center; gap:12px; }
.agri-pill { display:flex; flex-direction:column; align-items:flex-start; line-height:1.1;
	background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.22);
	border-radius:12px; padding:8px 14px; }
.agri-pill b { font-size:16px; } .agri-pill span { font-size:11px; opacity:.85; }
.agri-btn-new { background:#f6a609; color:#1a1a1a; border:none; font-weight:700;
	border-radius:12px; padding:11px 18px; cursor:pointer; box-shadow:0 4px 12px rgba(246,166,9,.4);
	transition:transform .15s ease, box-shadow .15s ease; }
.agri-btn-new:hover { transform:translateY(-1px); box-shadow:0 7px 18px rgba(246,166,9,.5); }

/* Card grid */
.agri-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:18px; margin-bottom:30px; }
@media (max-width:1100px){ .agri-cards{ grid-template-columns:repeat(2,1fr);} }
@media (max-width:640px){ .agri-cards{ grid-template-columns:1fr;} }
.agri-card { position:relative; background:#fff; border-radius:var(--card-radius);
	padding:22px; min-height:150px; box-shadow:0 4px 16px rgba(20,40,30,.07);
	border:1px solid #eef1f0; overflow:hidden; transition:transform .15s ease, box-shadow .15s ease; }
.agri-card:hover { transform:translateY(-3px); box-shadow:0 12px 28px rgba(20,40,30,.12); }
.agri-card::before { content:""; position:absolute; top:0; left:0; right:0; height:5px;
	background:var(--accent,#2f7df6); }
.agri-icon { width:46px; height:46px; border-radius:14px; display:flex; align-items:center;
	justify-content:center; font-size:20px; color:#fff; margin-bottom:18px; }
.agri-num { font-size:34px; font-weight:800; line-height:1; color:#0f1f17; }
.agri-card-title { font-size:14px; font-weight:600; margin-top:8px; }
.agri-card-sub { font-size:12px; color:#8a958d; margin-top:2px; }

/* accent helpers */
.c-blue{ --accent:var(--c-blue);} .c-blue .agri-icon{ background:var(--c-blue);}
.c-green{ --accent:var(--c-green);} .c-green .agri-icon{ background:var(--c-green);}
.c-orange{ --accent:var(--c-orange);} .c-orange .agri-icon{ background:var(--c-orange);}
.c-pink{ --accent:var(--c-pink);} .c-pink .agri-icon{ background:var(--c-pink);}
.c-teal{ --accent:var(--c-teal);} .c-teal .agri-icon{ background:var(--c-teal);}
.c-purple{ --accent:var(--c-purple);} .c-purple .agri-icon{ background:var(--c-purple);}

/* Recent activity card */
.agri-recent .agri-recent-head { display:flex; align-items:center; gap:10px; font-weight:700;
	font-size:14px; margin-bottom:14px; }
.agri-recent-row { display:flex; align-items:center; justify-content:space-between;
	padding:8px 0; border-bottom:1px solid #f1f3f2; font-size:13px; }
.agri-recent-row:last-child { border-bottom:none; }
.agri-recent-row .t { color:#33413a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
	max-width:160px; }
.agri-tag { font-size:10px; font-weight:700; letter-spacing:.4px; padding:3px 9px;
	border-radius:20px; text-transform:uppercase; }
.agri-tag.green{ background:#e7f6ee; color:#1c8a5a;} .agri-tag.gray{ background:#eef0ee; color:#5a655c;}
.agri-tag.blue{ background:#e7f0fe; color:#2f6fe0;} .agri-tag.orange{ background:#fff2df; color:#d98308;}

/* Analytics */
.agri-analytics-head { display:flex; align-items:center; gap:10px; font-size:18px;
	font-weight:700; margin:6px 0 16px; }
.agri-analytics { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:18px; }
@media (max-width:900px){ .agri-analytics{ grid-template-columns:1fr;} }
.agri-panel { position:relative; background:#fff; border-radius:var(--card-radius); padding:18px 20px;
	border:1px solid #eef1f0; box-shadow:0 4px 16px rgba(20,40,30,.07); overflow:hidden; }
.agri-panel::before { content:""; position:absolute; top:0; left:0; right:0; height:4px;
	background:var(--accent,#2f7df6); }
.agri-panel-title { font-weight:700; font-size:14px; margin-bottom:6px; }
.agri-panel-title small { color:#9aa39c; font-weight:500; margin-left:6px; }
</style>

<div class="agri-dash">
	<div class="agri-banner">
		<div class="agri-banner-left">
			<div class="agri-avatar">${frappe.utils.escape_html((name[0] || "A").toUpperCase())}</div>
			<div>
				<div class="agri-greeting">${greeting()}, ${frappe.utils.escape_html(name)}</div>
				<div class="agri-subtle">${dateLabel} &middot; Syova Seeds</div>
			</div>
		</div>
		<div class="agri-banner-right">
			<div class="agri-pill"><b id="agri-pill-num">&mdash;</b><span>${__("Active demo gardens")}</span></div>
			<button class="agri-btn-new" id="agri-new">+ ${__("New Activity")}</button>
		</div>
	</div>

	<div class="agri-cards">
		<div class="agri-card c-blue">
			<div class="agri-icon">&#128101;</div>
			<div class="agri-num" id="m-promoters">&mdash;</div>
			<div class="agri-card-title">${__("Active Field Promoters")}</div>
			<div class="agri-card-sub">${__("Currently active")}</div>
		</div>
		<div class="agri-card c-green">
			<div class="agri-icon">&#127793;</div>
			<div class="agri-num" id="m-gardens">&mdash;</div>
			<div class="agri-card-title">${__("Active Demo Gardens")}</div>
			<div class="agri-card-sub">${__("In the field")}</div>
		</div>
		<div class="agri-card c-orange">
			<div class="agri-icon">&#128221;</div>
			<div class="agri-num" id="m-activities">&mdash;</div>
			<div class="agri-card-title">${__("Field Activities")}</div>
			<div class="agri-card-sub">${__("This month")}</div>
		</div>
		<div class="agri-card c-pink agri-recent">
			<div class="agri-recent-head"><span class="agri-icon" style="width:30px;height:30px;border-radius:9px;font-size:14px;margin:0">&#8635;</span> ${__("Recent Activity")}</div>
			<div id="agri-recent"><div class="agri-recent-row"><span class="t">${__("Loading...")}</span></div></div>
		</div>
	</div>

	<div class="agri-analytics-head"><span class="agri-icon c-purple" style="background:var(--c-purple);width:30px;height:30px;border-radius:9px;font-size:14px;margin:0">&#128202;</span> ${__("Your analytics")}</div>

	<div class="agri-analytics">
		<div class="agri-panel c-blue"><div class="agri-panel-title">${__("Activity volume")}<small>${__("last 6 months")}</small></div><div id="agri-chart-line"></div></div>
		<div class="agri-panel c-green"><div class="agri-panel-title">${__("Status breakdown")}</div><div id="agri-chart-donut"></div></div>
	</div>
	<div class="agri-analytics">
		<div class="agri-panel c-orange"><div class="agri-panel-title">${__("Orders by month")}<small>${__("last 6 months")}</small></div><div id="agri-chart-bar"></div></div>
		<div class="agri-panel c-pink"><div class="agri-panel-title">${__("Demo gardens by status")}</div><div id="agri-chart-donut2"></div></div>
	</div>
</div>`;
}

function set_num(id, val) {
	const el = document.getElementById(id);
	if (el) el.textContent = (val === undefined || val === null) ? "0" : val;
}

function fill_metrics() {
	const month_start = frappe.datetime.month_start();
	const safe = (p) => p.catch(() => 0);

	safe(frappe.db.count("Field Promoter", { status: "Active" })).then((v) => set_num("m-promoters", v));
	safe(frappe.db.count("Demo Garden")).then((v) => {
		set_num("m-gardens", v);
		const pill = document.getElementById("agri-pill-num");
		if (pill) pill.textContent = v;
	});
	safe(frappe.db.count("Field Activity Log", { activity_date: [">=", month_start] }))
		.then((v) => set_num("m-activities", v));

	// New Activity button
	const btn = document.getElementById("agri-new");
	if (btn) btn.onclick = () => frappe.new_doc("Field Activity Log");
}

function fill_recent() {
	const box = document.getElementById("agri-recent");
	if (!box) return;
	frappe.db
		.get_list("Field Activity Log", {
			fields: ["name", "activity_type", "status"],
			order_by: "creation desc",
			limit: 5,
		})
		.then((rows) => {
			if (!rows || !rows.length) {
				box.innerHTML = `<div class="agri-recent-row"><span class="t">${__("No activity yet")}</span></div>`;
				return;
			}
			const tagClass = (s) =>
				({ Submitted: "blue", Approved: "green", Draft: "gray", Completed: "green" }[s] || "gray");
			box.innerHTML = rows
				.map(
					(r) => `<div class="agri-recent-row">
						<span class="t">${frappe.utils.escape_html(r.activity_type || r.name)}</span>
						<span class="agri-tag ${tagClass(r.status)}">${frappe.utils.escape_html(r.status || "—")}</span>
					</div>`
				)
				.join("");
		})
		.catch(() => {
			box.innerHTML = `<div class="agri-recent-row"><span class="t">${__("No activity yet")}</span></div>`;
		});
}

function render_charts() {
	// Sample data — UI structure focus. Wire to real aggregates later if desired.
	window.__agri_render_charts = function () {
		if (!frappe.Chart) return;
		const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];

		const line = document.getElementById("agri-chart-line");
		if (line) {
			line.innerHTML = "";
			new frappe.Chart(line, {
				type: "line", height: 230,
				colors: ["#2f7df6"],
				data: { labels: months, datasets: [{ values: [2, 3, 4, 3, 6, 8] }] },
				lineOptions: { regionFill: 1, hideDots: 0 },
			});
		}
		const donut = document.getElementById("agri-chart-donut");
		if (donut) {
			donut.innerHTML = "";
			new frappe.Chart(donut, {
				type: "donut", height: 230,
				colors: ["#22a06b", "#2f7df6", "#f6a609"],
				data: { labels: ["Approved", "Submitted", "Draft"], datasets: [{ values: [6, 3, 2] }] },
			});
		}
		const bar = document.getElementById("agri-chart-bar");
		if (bar) {
			bar.innerHTML = "";
			new frappe.Chart(bar, {
				type: "bar", height: 230,
				colors: ["#f6a609"],
				data: { labels: months, datasets: [{ values: [1, 2, 2, 4, 3, 5] }] },
			});
		}
		const donut2 = document.getElementById("agri-chart-donut2");
		if (donut2) {
			donut2.innerHTML = "";
			new frappe.Chart(donut2, {
				type: "donut", height: 230,
				colors: ["#13b4b1", "#ec4a7d", "#8b5cf6"],
				data: { labels: ["Planted", "Material Received", "Registered"], datasets: [{ values: [4, 2, 3] }] },
			});
		}
	};
	window.__agri_render_charts();
}
