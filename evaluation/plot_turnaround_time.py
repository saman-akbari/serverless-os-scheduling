from pathlib import Path

from helper.parsing_worker_logs import get_open_lambda_log_filename


# Ex: 2025/10/23 16:2dd4:00.399037 *** Request 19 1 2025-10-23 16:24:00.397986037 +0200 CEST m=+2.607554614
def is_turnaround_log_item(logline: str):
    # custom log lines created by manually changing OL server source code
    return "*** Request" in logline


def parse_turnaround_log_item(logline: str):
    parts = logline.split(" ")
    start_index = parts.index("***")
    request_id = parts[start_index + 2]
    turnaround_time = parts[start_index + 3]
    start_time = parts[4] + " " + parts[5]
    return request_id, turnaround_time, start_time


def get_turnaround_time(root: Path, plan_id: int, sched_cmd):
    log_file = root / "logs" / get_open_lambda_log_filename(root, plan_id, sched_cmd)
    if not log_file.exists():
        print(f"Log file does not exist: {log_file}")
        return []

    turnaround_times = []
    with open(log_file, "r") as f:
        for line in f:
            if is_turnaround_log_item(line):
                _, turnaround_time, _ = parse_turnaround_log_item(line)
                turnaround_times.append(int(turnaround_time) / 1000)  # convert ms -> s

    return turnaround_times
