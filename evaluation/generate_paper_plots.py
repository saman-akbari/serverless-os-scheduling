import argparse
import sys
from pathlib import Path

import matplotlib.lines as mlines
import matplotlib.ticker as ticker
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.legend_handler import HandlerTuple

sys.path.insert(0, str(Path(__file__).parent))

from helper.parsing_plan import get_plan_ids
from helper.parsing_sched_order import get_sched_command_order
from helper.storing import store_figure
from plot_ctxt_switches_over_time import get_context_switches_by_cmd
from helper.parsing_mp_stats import get_accumulated_vm_stats_by_cmd
from helper.parsing_scx_logs import did_sched_fail
from plot_exec_time import get_exec_time
from plot_queuing_time import get_queuing_time
from plot_turnaround_time import get_turnaround_time
from plot_user_costs import get_user_costs_by_cmd
from print_request_timeouts import get_failed_request_frac_per_cmd

CAT_COLORS = {
    "Linux": "#0d49fb",
    "Fairness": "#e6091c",
    "Central.": "#26eb47",
    "Affinity": "#8936df",
    "Deadline": "#fec32d",
}

CAT_ORDER = {"Linux": 0, "Fairness": 1, "Central.": 2, "Affinity": 3, "Deadline": 4}


def get_family_info(cmd: str):
    if "scx_simple" in cmd:
        return "Fairness", "simple"
    if "scx_prev" in cmd:
        return "Fairness", "prev"
    if "scx_flatcg" in cmd:
        return "Central.", "flatcg"
    if "scx_central" in cmd:
        return "Central.", "central"
    if "scx_tickless" in cmd:
        return "Central.", "tickless"
    if "scx_rusty" in cmd:
        return "Affinity", "rusty"
    if "scx_pair" in cmd:
        return "Affinity", "pair"
    if "scx_nest" in cmd:
        return "Affinity", "nest"
    if "scx_mitosis" in cmd:
        return "Affinity", "mitosis"
    if "scx_layered" in cmd:
        return "Affinity", "layered"
    if "scx_rustland" in cmd:
        return "Deadline", "rustland"
    if "scx_bpfland" in cmd:
        return "Deadline", "bpfland"
    if "scx_cosmos" in cmd:
        return "Deadline", "cosmos"
    if "scx_lavd" in cmd:
        return "Deadline", "lavd"
    if cmd == "EEVDF":
        return "Linux", "EEVDF"
    if cmd == "CFS":
        return "Linux", "CFS"
    if "SCHED_FIFO" in cmd:
        return "Linux", "FIFO"
    if "SCHED_RR" in cmd:
        return "Linux", "RR"
    return None, None


def _generate_and_print_stats(
        cmd: str, cat: str, short: str, timeout_frac: float, tds: list, qds: list, eds: list
):
    p_td = np.percentile(tds, [50, 75, 90, 95, 99])
    p_qd = np.percentile(qds, [50, 75, 90, 95, 99])
    p_ed = np.percentile(eds, [50, 75, 90, 95, 99])

    print(f"\nScheduler: {cmd}")
    print(
        f"  Category: {cat}, Short Name: {short}, Timeout Rate: {timeout_frac * 100:.2f}%"
    )
    print("  Metric          | p50    | p75    | p90    | p95    | p99")
    print("  ----------------------------------------------------------------")
    print(
        f"  Turnaround (s)  | {p_td[0]:<6.3f} | {p_td[1]:<6.3f} | {p_td[2]:<6.3f} | {p_td[3]:<6.3f} | {p_td[4]:<6.3f}"
    )
    print(
        f"  Queuing (s)     | {p_qd[0]:<6.3f} | {p_qd[1]:<6.3f} | {p_qd[2]:<6.3f} | {p_qd[3]:<6.3f} | {p_qd[4]:<6.3f}"
    )
    print(
        f"  Execution (s)   | {p_ed[0]:<6.3f} | {p_ed[1]:<6.3f} | {p_ed[2]:<6.3f} | {p_ed[3]:<6.3f} | {p_ed[4]:<6.3f}"
    )


def get_best_configs_per_family(
        root: Path, plan_id: int, strict_timeout: bool = True, show_stats: bool = False
) -> list:
    executed_cmds = get_sched_command_order(root)
    family_best = {}

    if show_stats:
        print("\n--- Percentile Data ---")
        print("=" * 70)

    for cmd in executed_cmds:
        if did_sched_fail(root, plan_id, cmd):
            continue

        cat, short = get_family_info(cmd)
        if not cat:
            continue

        tds = get_turnaround_time(root, plan_id, cmd)
        if tds is None or len(tds) == 0:
            continue

        timeout_frac = get_failed_request_frac_per_cmd(root, plan_id, cmd)

        if show_stats:
            qds = get_queuing_time(root, plan_id, cmd)
            eds = get_exec_time(root, plan_id, cmd)
            _generate_and_print_stats(cmd, cat, short, timeout_frac, tds, qds, eds)

        med_td = np.median(tds)

        family_key = (cat, short)

        if family_key not in family_best:
            family_best[family_key] = {"absolute": None, "strict": None}

        curr_abs = family_best[family_key]["absolute"]
        if curr_abs is None or med_td < curr_abs[1]:
            family_best[family_key]["absolute"] = (cmd, med_td)

        if timeout_frac <= 0.05:
            curr_strict = family_best[family_key]["strict"]
            if curr_strict is None or med_td < curr_strict[1]:
                family_best[family_key]["strict"] = (cmd, med_td)

    best_configs = []
    print(
        f"\n--- Selected Best Configurations (Strict={'Yes' if strict_timeout else 'No'}) ---"
    )
    for (cat, short), bests in family_best.items():
        if strict_timeout:
            if bests["strict"] is not None:
                cmd, med_td = bests["strict"]
                best_configs.append((cmd, cat, short))
                print(f"[{cat}] {short:15s} -> Median TD: {med_td:.3f}s | Cmd: {cmd}")
        else:
            chosen = (
                bests["strict"] if bests["strict"] is not None else bests["absolute"]
            )
            if chosen is not None:
                cmd, med_td = chosen
                best_configs.append((cmd, cat, short))
                print(f"[{cat}] {short:15s} -> Median TD: {med_td:.3f}s | Cmd: {cmd}")

    best_configs.sort(key=lambda x: (CAT_ORDER.get(x[1], 99), x[2]))
    return best_configs


def compute_x_positions(configs):
    x_positions = []
    current_x = 0
    if not configs:
        return []
    current_cat = configs[0][1]

    for c in configs:
        cat = c[1]
        if cat != current_cat:
            current_x += 45.0
            current_cat = cat
        x_positions.append(current_x)
        current_x += 30.0
    return x_positions


def compute_width(x_positions):
    if len(x_positions) < 2:
        return 1.0
    diffs = np.diff(sorted(x_positions))
    return np.min(diffs) * 0.5


def compute_xlim(x_positions):
    if len(x_positions) < 2:
        return x_positions[0] - 1, x_positions[0] + 1
    diffs = np.diff(sorted(x_positions))
    padding = np.min(diffs) * 0.8
    return min(x_positions) - padding, max(x_positions) + padding


def draw_x_axis_separators_and_labels(fig, ax, configs, x_positions):
    cats = {}
    boundaries = []
    current_cat = configs[0][1]

    for i, c in enumerate(configs):
        cat = c[1]
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(x_positions[i])

        if cat != current_cat:
            boundaries.append((x_positions[i - 1] + x_positions[i]) / 2)
            current_cat = cat

    fig.canvas.draw()
    max_height_px = (
        max(label.get_window_extent().height for label in ax.get_xticklabels())
        if ax.get_xticklabels()
        else 0
    )
    max_height_pts = max_height_px * 72 / fig.dpi

    text_offset_pts = -(max_height_pts + 35)
    line_offset_pts = text_offset_pts + 15

    for b in boundaries:
        ax.annotate(
            "",
            xy=(b, 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, line_offset_pts),
            textcoords="offset points",
            arrowprops=dict(arrowstyle="-", color="gray", lw=1.5),
            annotation_clip=False,
        )

    for cat, xs in cats.items():
        center = sum(xs) / len(xs)
        ax.annotate(
            cat,
            xy=(center, 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, text_offset_pts),
            textcoords="offset points",
            ha="center",
            va="top",
            fontweight="bold",
            color=CAT_COLORS[cat],
            fontsize=15,
            annotation_clip=False,
        )

    ax.set_xlabel(" ", labelpad=max_height_pts + 75)


def plot_context_switches(
        root: Path,
        plan_id: int,
        configs: list,
        x_positions: list,
        dynamic_width: float,
        short_labels: list,
):
    print("\n--- Plotting Context Switches ---")
    fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
    bar_colors = [CAT_COLORS[c[1]] for c in configs]
    total_ctxt = []

    for cmd, cat, short in configs:
        ctxt_data = get_context_switches_by_cmd(root, plan_id, cmd)
        total_ctxt.append(
            max(ctxt_data["y"]) if ctxt_data and len(ctxt_data["y"]) > 0 else 0
        )

    for (cmd, cat, short), v in zip(configs, total_ctxt):
        print(f"[{cat}] {short}: {v}")

    ax.bar(
        x_positions,
        total_ctxt,
        color=bar_colors,
        edgecolor="black",
        alpha=1.0,
        width=dynamic_width,
        zorder=2,
    )
    ax.set_xticks(x_positions)
    ax.set_xticklabels(short_labels, rotation=90, fontsize=16)
    ax.set_yticks([0, 1e6, 2e6, 3e6, 4e6])
    ax.set_ylabel("Context Switches")
    ax.grid(True, axis="y", linestyle="-", alpha=0.6)
    ax.set_ylim(0, 4e6)
    if x_positions:
        ax.set_xlim(*compute_xlim(x_positions))
    draw_x_axis_separators_and_labels(fig, ax, configs, x_positions)

    store_figure(root, "context-switches", with_timestamp=False)


def plot_timeout_rate(
        root: Path,
        plan_id: int,
        configs: list,
        x_positions: list,
        dynamic_width: float,
        short_labels: list,
):
    print("\n--- Plotting Timeout Rates (%) ---")
    fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
    bar_colors = [CAT_COLORS[c[1]] for c in configs]
    timeouts = [get_failed_request_frac_per_cmd(root, plan_id, c[0]) * 100 for c in configs]

    for (cmd, cat, short), t in zip(configs, timeouts):
        print(f"[{cat}] {short}: {t:.2f}%")

    bars = ax.bar(
        x_positions,
        timeouts,
        color=bar_colors,
        edgecolor="black",
        alpha=1.0,
        width=dynamic_width,
        zorder=2,
    )
    ax.bar_label(
        bars,
        labels=[f"{t:.1f}" if t > 0.1 else "" for t in timeouts],
        padding=3,
        fontsize=12,
        fontweight="bold",
    )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(short_labels, rotation=90, fontsize=16)
    ax.set_ylabel("Timeout Rate (\\%)")
    ax.set_ylim(0, 60)
    if x_positions:
        ax.set_xlim(*compute_xlim(x_positions))
    ax.grid(True, axis="y", linestyle="-", alpha=0.6)
    draw_x_axis_separators_and_labels(fig, ax, configs, x_positions)

    store_figure(root, "timeout-rate", with_timestamp=False)


def plot_system_overhead(
        root: Path,
        plan_id: int,
        configs: list,
        x_positions: list,
        dynamic_width: float,
        short_labels: list,
):
    print("\n--- Plotting CPU Utilization & Steal Rate (%) ---")
    fig, ax = plt.subplots(figsize=(6.5, 4.1), constrained_layout=True)
    usr_pct, sys_pct, idle_pct, steal_pct = [], [], [], []
    usr_raw, sys_raw, idle_raw, steal_raw = [], [], [], []

    for cmd, _, _ in configs:
        stats = get_accumulated_vm_stats_by_cmd(root, plan_id, cmd)
        u, s, st, i = (
            stats["usr"] + stats.get("nice", 0),
            stats["sys"],
            stats["steal"],
            stats["idle"],
        )
        vm_total, absolute_total = u + s + i, u + s + i + st

        usr_raw.append(u)
        sys_raw.append(s)
        idle_raw.append(i)
        steal_raw.append(st)

        if vm_total > 0:
            usr_pct.append((u / vm_total) * 100)
            sys_pct.append((s / vm_total) * 100)
            idle_pct.append((i / vm_total) * 100)
        else:
            usr_pct.append(0)
            sys_pct.append(0)
            idle_pct.append(0)

        steal_pct.append((st / absolute_total) * 100 if absolute_total > 0 else 0)

    usr_pct, sys_pct, idle_pct = (
        np.array(usr_pct),
        np.array(sys_pct),
        np.array(idle_pct),
    )

    for i, (cmd, cat, short) in enumerate(configs):
        print(
            f"[{cat}] {short} | User: {usr_pct[i]:.2f}% ({usr_raw[i]:.2f}s), "
            f"Kernel: {sys_pct[i]:.2f}% ({sys_raw[i]:.2f}s), "
            f"Idle: {idle_pct[i]:.2f}% ({idle_raw[i]:.2f}s), "
            f"Steal: {steal_pct[i]:.2f}% ({steal_raw[i]:.2f}s)"
        )

    ax.bar(
        x_positions,
        usr_pct,
        width=dynamic_width,
        label="User %",
        color="#000000",
        alpha=1.0,
        zorder=2,
    )
    ax.bar(
        x_positions,
        sys_pct,
        width=dynamic_width,
        bottom=usr_pct,
        label="Kernel %",
        color="#e6091c",
        alpha=1.0,
        zorder=2,
    )
    ax.bar(
        x_positions,
        idle_pct,
        width=dynamic_width,
        bottom=usr_pct + sys_pct,
        label="Idle %",
        color="#e0e0e0",
        alpha=1.0,
        zorder=2,
    )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(short_labels, rotation=90, fontsize=16)
    ax.set_ylabel("VM CPU Utilization (\\%)")
    ax.set_ylim(0, 100)
    ax.grid(True, axis="y", linestyle="-", alpha=0.6)
    if x_positions:
        ax.set_xlim(*compute_xlim(x_positions))
    draw_x_axis_separators_and_labels(fig, ax, configs, x_positions)

    ax2 = ax.twinx()
    ax2.plot(
        x_positions,
        steal_pct,
        color="darkorange",
        marker="o",
        linestyle="-.",
        linewidth=3,
        markersize=10,
        label="Steal Rate",
        zorder=5,
    )
    ax2.set_ylabel("Hypervisor Steal Rate (\\%)", color="darkorange", fontweight="bold")
    ax2.tick_params(axis="y", labelcolor="darkorange")
    ax2.spines["right"].set_visible(True)
    ax2.set_yticks([0, 5, 10])
    ax2.set_ylim(0, 10)

    lines_1, labels_1 = ax.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax.legend(
        lines_1 + lines_2,
        labels_1 + labels_2,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.03),
        ncol=4,
    )

    store_figure(root, "system-overhead", with_timestamp=False)


def _get_metric_data_and_best_indices(
        root: Path, plan_id: int, configs: list, fetch_func
):
    data_box = []
    best_idx = set()
    categories = set(c[1] for c in configs)

    for cmd, _, _ in configs:
        data_box.append(fetch_func(root, plan_id, cmd))

    for cat in categories:
        cat_indices = [j for j, c in enumerate(configs) if c[1] == cat]
        valid_indices = [j for j in cat_indices if len(data_box[j]) > 0]
        if valid_indices:
            best_idx.add(min(valid_indices, key=lambda j: np.median(data_box[j])))

    return data_box, best_idx


def _render_latency_plot(
        root: Path,
        configs: list,
        x_positions: list,
        dynamic_width: float,
        short_labels: list,
        data_box: list,
        best_idx: set,
        y_label: str,
        file_name: str,
):
    print(f"\n--- Latency Lifecycle Stats ({y_label}) ---")
    for j, c in enumerate(configs):
        d = data_box[j]
        if len(d) > 0:
            print(
                f"  [{c[1]}] {c[2]}: Median={np.median(d):.4f}, Min={np.min(d):.4f}, Max={np.max(d):.4f}"
            )
        else:
            print(f"  [{c[1]}] {c[2]}: No data")

    fig, axs = plt.subplots(
        2,
        1,
        figsize=(6, 6.5),
        gridspec_kw={"height_ratios": [1.2, 1]},
        constrained_layout=True,
    )
    max_val = max([max(d) if len(d) > 0 else 1 for d in data_box])
    min_val = min([min(d) if len(d) > 0 else 1e-3 for d in data_box])
    y_bound_max = max(1e3, max_val * 2.0)
    y_bound_min = min(1e-3, min_val * 0.5)

    axs[0].set_ylim(y_bound_min, y_bound_max)
    if x_positions:
        axs[0].set_xlim(*compute_xlim(x_positions))

    for j, c in enumerate(configs):
        if j in best_idx:
            best_x = x_positions[j]
            axs[0].axvspan(
                best_x - dynamic_width,
                best_x + dynamic_width,
                facecolor="lightgray",
                alpha=0.5,
                zorder=0,
            )
            axs[0].plot(
                best_x,
                0.95,
                marker="*",
                color="gold",
                markersize=dynamic_width * 1.2,
                markeredgecolor="darkgoldenrod",
                transform=axs[0].get_xaxis_transform(),
                zorder=5,
                clip_on=False,
            )

    bplot = axs[0].boxplot(
        data_box,
        positions=x_positions,
        vert=True,
        showfliers=False,
        patch_artist=True,
        widths=dynamic_width,
        zorder=2,
    )

    for j, patch in enumerate(bplot["boxes"]):
        cat_color = CAT_COLORS[configs[j][1]]
        patch.set_facecolor(cat_color)
        patch.set_alpha(1.0)
        patch.set_edgecolor(cat_color)
        patch.set_linewidth(1.5)

    for median in bplot["medians"]:
        median.set_color("black")
        median.set_linewidth(2)

    for element in ["whiskers", "caps"]:
        for line in bplot[element]:
            line.set_color("black")

    log_formatter = ticker.LogFormatterMathtext()

    axs[0].set_xticks(x_positions)
    axs[0].set_xticklabels(short_labels, rotation=90, fontsize=16)
    axs[0].set_ylabel(y_label, fontsize=20)
    axs[0].set_yscale("log")
    axs[0].yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=10))
    axs[0].yaxis.set_minor_locator(
        ticker.LogLocator(base=10.0, subs="all", numticks=100)
    )
    axs[0].yaxis.set_major_formatter(log_formatter)
    axs[0].grid(True, axis="y", which="major", linestyle="-", alpha=0.6)
    draw_x_axis_separators_and_labels(fig, axs[0], configs, x_positions)

    for j, c in enumerate(configs):
        if j in best_idx:
            axs[1].ecdf(
                data_box[j],
                label=c[2],
                color=CAT_COLORS[c[1]],
                linewidth=2.5,
                alpha=0.9,
                zorder=3,
            )

    axs[1].set_xscale("log")
    axs[1].set_xlim(y_bound_min, 10e2)
    axs[1].xaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=10))
    axs[1].xaxis.set_major_formatter(log_formatter)
    axs[1].set_xlabel(y_label)
    axs[1].set_ylabel("CDF", fontsize=20)
    axs[1].set_ylim(0, 1.0)
    axs[1].set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    axs[1].grid(True, which="major", linestyle="-", alpha=0.6)
    axs[1].legend(
        loc="lower right", fontsize=16, bbox_to_anchor=(1.0, -0.09), labelspacing=0.2
    )

    store_figure(root, file_name, with_timestamp=False)


def plot_queuing_time(
        root: Path,
        plan_id: int,
        configs: list,
        x_positions: list,
        dynamic_width: float,
        short_labels: list,
):
    data_box, best_idx = _get_metric_data_and_best_indices(
        root, plan_id, configs, get_queuing_time
    )
    _render_latency_plot(
        root,
        configs,
        x_positions,
        dynamic_width,
        short_labels,
        data_box,
        best_idx,
        "Queuing Time (s)",
        "queuing-time",
    )


def plot_execution_time(
        root: Path,
        plan_id: int,
        configs: list,
        x_positions: list,
        dynamic_width: float,
        short_labels: list,
):
    data_box, best_idx = _get_metric_data_and_best_indices(
        root, plan_id, configs, get_exec_time
    )
    _render_latency_plot(
        root,
        configs,
        x_positions,
        dynamic_width,
        short_labels,
        data_box,
        best_idx,
        "Execution Time (s)",
        "exec-time",
    )


def plot_turnaround_time(
        root: Path,
        plan_id: int,
        configs: list,
        x_positions: list,
        dynamic_width: float,
        short_labels: list,
):
    data_box, best_idx = _get_metric_data_and_best_indices(
        root, plan_id, configs, get_turnaround_time
    )
    _render_latency_plot(
        root,
        configs,
        x_positions,
        dynamic_width,
        short_labels,
        data_box,
        best_idx,
        "Turnaround Time (s)",
        "turnaround-time",
    )


def plot_cost_performance(root: Path, plan_id: int, configs: list):
    print("\n--- Plotting User Costs & Performance Pareto ---")
    fig, axs = plt.subplots(1, 2, figsize=(8, 4), constrained_layout=True)

    valid_points = []
    labels = []
    costs = []
    colors = []

    for cmd, cat, short in configs:
        cost = get_user_costs_by_cmd(root, plan_id, cmd)
        tds = get_turnaround_time(root, plan_id, cmd)

        if cost is not None and cost > 0:
            labels.append(short)
            costs.append(cost)
            colors.append(CAT_COLORS[cat])

            if tds:
                med_td = np.median(tds)
                if med_td > 0:
                    valid_points.append((cost, med_td, cmd, cat, short))

    labels.reverse()
    costs.reverse()
    colors.reverse()

    custom_xticks = [0, 10, 20, 30, 40, 50]
    custom_xlim = 50

    bars = axs[0].barh(
        labels, costs, color=colors, edgecolor="black", alpha=1.0, height=0.6, zorder=2
    )
    axs[0].bar_label(bars, fmt="\\$%.2f", padding=5, fontsize=14)

    axs[0].set_xticks(custom_xticks)
    axs[0].set_xlim(0, custom_xlim)
    axs[0].grid(True, axis="x", linestyle="-", alpha=0.6)
    axs[0].tick_params(axis="y", labelsize=18)

    AVAILABLE_MARKERS = ["o", "s", "^", "D", "P", "X", "v", "<", ">", "H", "d", "p"]
    cat_marker_map = {}
    for pt in valid_points:
        cat, short = pt[3], pt[4]
        if cat not in cat_marker_map:
            cat_marker_map[cat] = {}
        if short not in cat_marker_map[cat]:
            cat_marker_map[cat][short] = AVAILABLE_MARKERS[
                len(cat_marker_map[cat]) % len(AVAILABLE_MARKERS)
                ]

    pareto_points = sorted(valid_points, key=lambda x: x[0])
    pareto_c, pareto_t = [], []
    min_t = float("inf")
    pareto_cmds = set()
    pareto_shorts = set()

    for c, t, cmd, cat, short in pareto_points:
        if t < min_t:
            pareto_c.append(c)
            pareto_t.append(t)
            min_t = t
            pareto_cmds.add(cmd)
            pareto_shorts.add(short)

    for c, t, cmd, cat, short in valid_points:
        is_p = cmd in pareto_cmds
        print(
            f"[{cat}] {short} | Cost: ${c:.2f}, Median TD: {t:.4f}s | Pareto: {'Yes' if is_p else 'No'}"
        )

    pareto_bg_color = "wheat"

    for c, t, cmd, cat, short in valid_points:
        orig_m = cat_marker_map[cat][short]
        c_color = CAT_COLORS[cat]
        is_pareto = cmd in pareto_cmds
        is_linux = cat == "Linux"

        if is_pareto:
            axs[1].scatter(
                c, t, color=pareto_bg_color, marker="o", s=500, alpha=0.9, zorder=3
            )
            axs[1].scatter(
                c,
                t,
                color=c_color,
                marker=orig_m,
                s=100,
                edgecolor="black",
                linewidth=1.2,
                zorder=5,
            )
        elif is_linux:
            axs[1].scatter(
                c,
                t,
                color=c_color,
                marker=orig_m,
                s=90,
                alpha=0.9,
                edgecolor="black",
                linewidth=1.2,
                zorder=4,
            )
        else:
            axs[1].scatter(
                c,
                t,
                color=c_color,
                marker=orig_m,
                s=50,
                alpha=0.25,
                edgecolor="black",
                linewidth=0.8,
                zorder=3,
            )

    if pareto_c:
        axs[1].plot(
            pareto_c,
            pareto_t,
            linestyle="-",
            color=pareto_bg_color,
            linewidth=6.0,
            alpha=0.7,
            zorder=1,
        )
        axs[1].plot(
            pareto_c,
            pareto_t,
            linestyle="--",
            color="black",
            linewidth=2.0,
            alpha=0.8,
            zorder=2,
        )
        axs[1].annotate(
            "Pareto Front",
            xy=(pareto_c[-1], pareto_t[-1]),
            xytext=(5, -25),
            textcoords="offset points",
            ha="right",
            va="top",
            fontsize=14,
            fontweight="bold",
            color="black",
            zorder=6,
            bbox=dict(
                boxstyle="round,pad=0.4",
                fc="white",
                ec=pareto_bg_color,
                alpha=0.9,
                lw=2.0,
            ),
        )

    axs[1].set_xticks(custom_xticks)
    axs[1].set_xlim(0, custom_xlim)

    axs[1].set_ylim(bottom=0)
    axs[1].yaxis.set_major_locator(ticker.MaxNLocator(nbins=4, prune=None))
    fig.canvas.draw()
    y_ticks = axs[1].get_yticks()
    if len(y_ticks) > 1:
        axs[1].set_ylim(0, y_ticks[-1])

    axs[1].set_ylabel("Median Turnaround Time (s)")
    axs[1].grid(True, linestyle="-", alpha=0.6)

    fig.supxlabel("User Cost per 1M Function Calls (USD)", y=-0.12)

    columns_dict = {}
    ordered_cats = [
        c
        for c in sorted(CAT_ORDER.keys(), key=lambda k: CAT_ORDER[k])
        if c in [p[3] for p in valid_points]
    ]
    empty_handle = mlines.Line2D([], [], linestyle="none")

    for cat in ordered_cats:
        cat_pts = [p for p in valid_points if p[3] == cat]
        col = []
        display_name = "Centralized" if cat == "Central." else cat
        col.append((empty_handle, r"\textbf{" + display_name + "}"))

        for c, t, cmd, _, short in cat_pts:
            orig_m = cat_marker_map[cat][short]
            c_color = CAT_COLORS[cat]
            is_pareto = cmd in pareto_cmds
            is_linux = cat == "Linux"

            if is_pareto:
                bg_patch = mlines.Line2D(
                    [],
                    [],
                    color="none",
                    marker="o",
                    markerfacecolor=pareto_bg_color,
                    markeredgecolor="none",
                    markersize=14,
                )
                main_line = mlines.Line2D(
                    [],
                    [],
                    color="none",
                    marker=orig_m,
                    markerfacecolor=c_color,
                    markeredgecolor="black",
                    markersize=8,
                )
                col.append(((bg_patch, main_line), short))
            elif is_linux:
                proxy = mlines.Line2D(
                    [],
                    [],
                    color="none",
                    marker=orig_m,
                    markerfacecolor=c_color,
                    markeredgecolor="black",
                    markersize=8,
                    alpha=0.9,
                )
                col.append((proxy, short))
            else:
                proxy = mlines.Line2D(
                    [],
                    [],
                    color="none",
                    marker=orig_m,
                    markerfacecolor=c_color,
                    markeredgecolor="black",
                    markersize=8,
                    alpha=0.3,
                )
                col.append((proxy, short))

        columns_dict[cat] = col

    columns_list = [columns_dict[cat] for cat in ordered_cats]
    max_rows = max(len(col) for col in columns_list) if columns_list else 0
    legend_handles, legend_labels = [], []

    for col in columns_list:
        while len(col) < max_rows:
            col.append((empty_handle, ""))
        for handle, label in col:
            legend_handles.append(handle)
            legend_labels.append(label)

    leg = fig.legend(
        legend_handles,
        legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.05),
        ncol=len(columns_list),
        frameon=False,
        borderaxespad=0.0,
        columnspacing=1.5,
        handletextpad=0.5,
        handler_map={tuple: HandlerTuple(ndivide=1, pad=0)},
        prop={"size": 14},
    )

    for text in leg.get_texts():
        if text.get_text() in pareto_shorts:
            text.set_bbox(
                dict(
                    facecolor=pareto_bg_color,
                    edgecolor="none",
                    boxstyle="round,pad=0.25",
                    alpha=0.7,
                )
            )
            text.set_fontweight("bold")

    store_figure(root, "cost-performance", with_timestamp=False)


def main():
    parser = argparse.ArgumentParser(
        description="Generate cohesive, publication-ready plots."
    )
    parser.add_argument(
        "results_dir", type=str, nargs="?", default="../results/paper"
    )
    args = parser.parse_args()
    results_path = Path(args.results_dir)

    print("--- Starting Consolidated Paper Plot Generation ---")
    print(f"Results Directory: {results_path}")
    print(f"Output will be saved in: {results_path / 'figures'}")

    plt.style.use(Path(__file__).parent / "scientific.mplstyle")

    plan_ids = get_plan_ids(results_path)
    plan_id = plan_ids[0]

    configs_loose = get_best_configs_per_family(
        results_path, plan_id, strict_timeout=False, show_stats=False
    )
    x_positions_loose = compute_x_positions(configs_loose)
    dynamic_width_loose = compute_width(x_positions_loose)
    short_labels_loose = [c[2] for c in configs_loose]

    configs_strict = get_best_configs_per_family(
        results_path, plan_id, strict_timeout=True
    )
    x_positions_strict = compute_x_positions(configs_strict)
    dynamic_width_strict = compute_width(x_positions_strict)
    short_labels_strict = [c[2] for c in configs_strict]

    plot_context_switches(
        results_path,
        plan_id,
        configs_loose,
        x_positions_loose,
        dynamic_width_loose,
        short_labels_loose,
    )
    plot_timeout_rate(
        results_path,
        plan_id,
        configs_loose,
        x_positions_loose,
        dynamic_width_loose,
        short_labels_loose,
    )
    plot_system_overhead(
        results_path,
        plan_id,
        configs_loose,
        x_positions_loose,
        dynamic_width_loose,
        short_labels_loose,
    )

    plot_queuing_time(
        results_path,
        plan_id,
        configs_strict,
        x_positions_strict,
        dynamic_width_strict,
        short_labels_strict,
    )
    plot_execution_time(
        results_path,
        plan_id,
        configs_strict,
        x_positions_strict,
        dynamic_width_strict,
        short_labels_strict,
    )
    plot_turnaround_time(
        results_path,
        plan_id,
        configs_strict,
        x_positions_strict,
        dynamic_width_strict,
        short_labels_strict,
    )

    plot_cost_performance(results_path, plan_id, configs_strict)

    print("\n--- All paper plots generated successfully! ---")


if __name__ == "__main__":
    main()
