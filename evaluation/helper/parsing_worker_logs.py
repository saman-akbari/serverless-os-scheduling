from datetime import datetime

from .parsing_sched_order import Path, get_sched_log_name


def get_open_lambda_log_filename(root: Path, plan_id: int, sched_command: str) -> str:
    """Get the filename for a given plan_id & scheduler command combination"""
    sched_log_name = get_sched_log_name(root, sched_command)

    return f"plan{plan_id}_{sched_log_name}_run{0}_ol.logs"


def get_open_lambda_request_log_data(root: Path, plan_id: int, sched_cmd: str) -> dict:
    """Parses the logged Invoke times for each request_id from the OL logs

    Background:
    OL logging was adjusted to print the start time and total turnaround time with their respective request_id
    For more information look into server.py and stats.py in ../open-lambda/override
    """
    log_file = root / "logs" / get_open_lambda_log_filename(root, plan_id, sched_cmd)

    if not log_file.exists():
        print(f"WARNING: Log file does not exist: {log_file}")
        return None

    entries = {
        "requestId": [],  # id refers to id in the plan
        "startTime": [],  # Ex: 2025-10-23 16:24:00.397986037
        "turnaroundTime": [],
    }

    with open(log_file, "r") as f:
        for line in f:
            if _is_turnaround_log_item(line):
                request_id, turnaround_time, start_time = _parse_open_lambda_log_item(line)

                entries["requestId"].append(request_id)
                entries["startTime"].append(start_time)
                entries["turnaroundTime"].append(turnaround_time)

    return entries


# Ex: 2025/10/23 16:2dd4:00.399037 *** Request 19 1 2025-10-23 16:24:00.397986037 +0200 CEST m=+2.607554614
def _is_turnaround_log_item(logline: str):
    """Determine if a log line in the worker logs is associated with our manual changes.

    OpenLambda returns custom log lines due to manually changing Openlambda source code.
    """
    return "*** Request" in logline


def _parse_open_lambda_log_item(logline: str):
    """Parses a custom log line in the worker logs file introduced by our measurement"""
    parts = logline.split(" ")
    start_index = parts.index("***")
    request_id = parts[start_index + 2]
    turnaround_time = parts[start_index + 3]
    start_time_string = parts[start_index + 4] + " " + parts[start_index + 5]
    return request_id, turnaround_time, _parse_ol_start_time(start_time_string)


def _parse_ol_start_time(date_string: str) -> datetime:
    """Parses date_string part of a custom logline in the worker out"""
    assert (
            len(date_string) >= 21
    ), f"Expected date to have length of at least 21, Got: {len(date_string)} "
    return datetime.strptime(date_string[0:25], "%Y-%m-%d %H:%M:%S.%f")
