from pathlib import Path

from helper.parsing_load_instance_results import get_result_data


def get_exec_time(root: Path, plan_id: int, sched_name):
    df = get_result_data(root, plan_id, sched_name)
    df.dropna(inplace=True)
    return df["execDuration"].to_list()
