from pathlib import Path
from typing import Any

from helper.parsing_load_instance_results import get_result_data


def get_user_costs_by_cmd(root: Path, plan_id: int, sched_cmd: str) -> Any:
    # get accumulated functions
    results = get_result_data(root, plan_id, sched_cmd)

    exec_durations = results["execDuration"].dropna().to_list()
    total_measurements = len(exec_durations)

    # generate new sample
    total_functions = 10 ** 6
    sample = []
    for func_id in range(total_functions):
        idx = func_id % total_measurements
        sample.append(exec_durations[idx])

    total_exec_durations = sum(sample)

    # Europe (Frankfurt) x86 Price for first First 6 Billion GB-seconds / month
    # $0.0000166667 for every GB-second	$0.20 per 1M requests
    # $0.20 per 1M requests
    costs_per_gb_sec = 0.0000166667
    costs_per_100_mb_sec = costs_per_gb_sec / 10
    costs_per_1m_requests = 0.2

    return total_exec_durations * costs_per_100_mb_sec + costs_per_1m_requests
