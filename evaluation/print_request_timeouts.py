from pathlib import Path

from helper.parsing_load_instance_results import get_result_data
from helper.parsing_plan import get_plan


def get_failed_request_frac_per_cmd(root: Path, plan_id: int, sched_cmd: str) -> float:
    plan = get_plan(root, plan_id)
    total_requests = plan.shape[0]
    result = get_result_data(root, plan_id, sched_cmd)
    failed_request_count = result["startTimestamp"].isna().sum() + (
            total_requests - result.shape[0]
    )
    return failed_request_count / total_requests
