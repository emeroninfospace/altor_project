frappe.views.calendar["Project"] = {
    field_map: {
        start: "expected_start_date",
        end: "expected_end_date",
        id: "name",
        title: "project_name",
        progress: "percent_complete",
        priority: "priority"
    },
    gantt: {
        field_map: {
            start: "expected_start_date",
            end: "expected_end_date",
            id: "name",
            title: function(item) {
                const percent = item.percent_complete || 0;
                return `${item.project_name} (${percent}%)`;
            },
            progress: "percent_complete",
            priority: "priority"
        },
        order_by: "expected_start_date"
    },
    format_title: function(item) {
        const percent = item.percent_complete || 0;
        return `${item.project_name} (${percent}%)`;
    },
    priority_colors: {
        "High": "#ff5858",
        "Medium": "#ffa00a",
        "Low": "#98d85b"
    },
    get_priority_color: function(priority) {
        return frappe.views.calendar["Project"].priority_colors[priority] || "#7575ff";
    }
};

frappe.views.GanttView.prototype.prepare_tasks = function() {
    var me = this;

    var project_tasks = this.data.map(function(item) {
        var progress = item.percent_complete || 0;
        var label = `${item.project_name} (${progress}%)`;
        var color = frappe.views.calendar["Project"].get_priority_color(item.priority);
        return {
            start: item.expected_start_date,
            end: item.expected_end_date,
            name: label,
            id: item.name,
            progress: progress / 100,
            dependencies: "",
            custom_class: "color-" + color.substr(1) + " project-bar",
            _is_project: true
        };
    });

    var project_names = this.data.map(d => d.name);

    if (project_names.length === 0) {
        this.tasks = project_tasks;
        me.render_gantt();
        return;
    }

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Task",
            filters: { project: ["in", project_names] },
            fields: [
                "name", "subject", "exp_start_date", "exp_end_date",
                "progress", "project", "depends_on_tasks",
                "is_milestone", "parent_task"
            ],
            order_by: "project asc, parent_task IS NULL DESC, parent_task asc, exp_start_date asc"
        },
        callback: function(r) {
            var task_items = (r.message || []).map(function(task) {
                var indent = task.parent_task ? "         └─ " : "   ↳ ";
                var task_label = `${indent}${task.subject} (${task.progress || 0}%)`;

                var custom_class = "task-bar";
                if (task.is_milestone) custom_class += " bar-milestone";

                return {
                    start: task.exp_start_date,
                    end: task.exp_end_date,
                    name: task_label,
                    id: "T-" + task.name,
                    progress: (task.progress || 0) / 100,
                    dependencies: task.depends_on_tasks || "",
                    custom_class: custom_class,
                    project: task.project,
                    parent_task: task.parent_task || null
                };
            });

            var all_tasks = [];

            me.data.sort(function(a, b) {
                if (!a.expected_start_date && !b.expected_start_date) return 0;
                if (!a.expected_start_date) return 1;
                if (!b.expected_start_date) return -1;
                return a.expected_start_date.localeCompare(b.expected_start_date);
            });

            me.data.forEach(function(proj) {
                var proj_task = project_tasks.find(pt => pt.id === proj.name);
                if (proj_task) all_tasks.push(proj_task);

                task_items
                    .filter(t => t.project === proj.name)
                    .forEach(t => all_tasks.push(t));
            });

            me.tasks = all_tasks;
            me.render_gantt();
        }
    });

    this.tasks = project_tasks;
};

frappe.views.GanttView.prototype.set_colors = function() {
    var color_classes = [];
    this.tasks.forEach(t => {
        if (t.custom_class) {
            var parts = t.custom_class.split(" ");
            parts.forEach(c => {
                if (c.startsWith("color-")) color_classes.push(c);
            });
        }
    });

    let style = [...new Set(color_classes)].map(c => {
        const bar_color = "#" + c.substr(6);
        const progress_color = frappe.ui.color.get_contrast_color(bar_color);
        return `
            .gantt .bar-wrapper.${c} .bar {
                fill: ${bar_color};
            }
            .gantt .bar-wrapper.${c} .bar-progress {
                fill: ${progress_color};
            }
        `;
    }).join("");

    style += `
        /* Project bars - bold and colored */
        .gantt .bar-wrapper.project-bar .bar {
            stroke: #000;
            stroke-width: 3px;
            rx: 8px;
            ry: 8px;
        }
        .gantt .bar-wrapper.project-bar .bar-progress {
            rx: 8px;
            ry: 8px;
        }
        .gantt .bar-wrapper.project-bar .bar-label {
            font-weight: bold;
            fill: #000;
            font-size: 14px;
        }

        /* Task bars - light white/gray shade */
        .gantt .bar-wrapper.task-bar .bar {
            fill: #f8f9fa;         
            stroke: #dee2e6;       
            stroke-width: 1px;
            rx: 4px;
            ry: 4px;
        }
        .gantt .bar-wrapper.task-bar .bar-progress {
            fill: #007bff;          
            rx: 4px;
            ry: 4px;
        }
        .gantt .bar-wrapper.task-bar .bar-label {
            font-weight: normal;
            fill: #495057;          
            font-size: 12px;
        }

        /* Milestones - keep yellow highlight */
        .gantt .bar-wrapper.bar-milestone .bar {
            fill: #ffc107 !important;
            stroke: #e0a800;
        }

        /* Priority legend */
        .priority-legend {
            display: flex;
            gap: 15px;
            margin: 10px 0;
            padding: 10px;
            background: var(--bg-color);
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }
        .priority-item {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
        }
        .priority-color {
            width: 12px;
            height: 12px;
            border-radius: 2px;
        }
    `;

    style = `<style>${style}</style>`;
    this.$result.find("style.gantt-custom-style").remove();
    this.$result.prepend($(style).addClass("gantt-custom-style"));

    this.add_priority_legend();
};

frappe.views.GanttView.prototype.add_priority_legend = function() {
    if (this.doctype !== 'Project') return;

    this.$result.find('.priority-legend').remove();

    const colors = frappe.views.calendar["Project"].priority_colors;
    let legendHtml = '<div class="priority-legend">';

    for (const [priority, color] of Object.entries(colors)) {
        legendHtml += `
            <div class="priority-item">
                <div class="priority-color" style="background-color: ${color};"></div>
                <span>${priority}</span>
            </div>
        `;
    }

    legendHtml += '</div>';
    this.$result.find('.gantt-container').before(legendHtml);
};