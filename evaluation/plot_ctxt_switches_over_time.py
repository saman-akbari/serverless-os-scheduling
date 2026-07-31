from datetime import datetime
from pathlib import Path
from typing import Any

from helper.parsing_sched_order import get_sched_log_name


def parse_log_line(log_line: str):
    # Ex: 2025-11-17 00:41:11+01:00 33197396\n
    parts = log_line.split(" ")
    datetime_str = parts[0] + parts[1]
    ctxt = int(parts[2].replace("\n", ""))

    return datetime_str, ctxt


def get_system_ctxt_log_name(root: Path, plan_id: int, sched_cmd: str):
    sched_log_name = get_sched_log_name(root, sched_cmd)
    return f"plan{plan_id}_{sched_log_name}_run{0}_system-ctxt.logs"


def get_context_switches_by_cmd(root: Path, plan_id: int, sched_cmd: str) -> dict[str, Any]:
    log_filepath = root / "logs" / get_system_ctxt_log_name(root, plan_id, sched_cmd)

    result = {"x": [], "y": []}

    with open(log_filepath, "r") as f:
        for log_line in f.readlines():
            dt_string, ctxt = parse_log_line(log_line)
            dt = datetime.strptime(dt_string, "%Y-%m-%d%H:%M:%S%z")
            result["x"].append(dt)
            result["y"].append(ctxt)

    min_dt = min(result["x"])
    result["x"] = list(map(lambda d: (d - min_dt).total_seconds(), result["x"]))

    min_ctxt = min(result["y"])
    result["y"] = list(map(lambda c: c - min_ctxt, result["y"]))

    return result
