from datetime import datetime
from pathlib import Path

import numpy as np
from helper.parsing_load_instance_results import get_result_data
from helper.parsing_plan import get_plan
from helper.parsing_worker_logs import get_open_lambda_request_log_data


def get_queuing_time(root: Path, plan_id: int, sched_cmd: str) -> list[float]:
    """Returns the queuing times of a sched_cmd

    The queuing time for each request_id is determined by
    subtracting the logged start time of OpenLambda's route handler
    from the execution start time logged by the serverless function.
    The route handler logs the start time because of code changes to the OpenLambda
    For more information look into server.py and stats.py in ../open-lambda/override
    """
    queuing_times = []
    plan = get_plan(root, plan_id)
    ol_logs = get_open_lambda_request_log_data(root, plan_id, sched_cmd)

    if ol_logs is None:
        return []

    result_logs = get_result_data(root, plan_id, sched_cmd)
    total_requests = plan.shape[0]
    for request_id in range(total_requests):
        if str(request_id) not in ol_logs["requestId"]:
            continue

        start_time_idx = ol_logs["requestId"].index(str(request_id))
        start_time_at_ol = ol_logs["startTime"][start_time_idx]

        # time when serverless function has executed for the first time
        tmp = result_logs.loc[result_logs["requestIndex"] == request_id]["startTimestamp"]

        if len(tmp) == 0:
            print(f"WARNING: resultLog was empty for a rid={request_id}")
            continue

        exec_start_timestamp_string = tmp.iloc[0]  # Ex: 1.763124e+09
        if np.isnan(exec_start_timestamp_string):
            print("WARN: Encountered nan value in resultLogs")
            continue

        exec_start_time = datetime.fromtimestamp(exec_start_timestamp_string)
        queuing_time = exec_start_time - start_time_at_ol

        if queuing_time.total_seconds() > 3600:
            queuing_times.append(queuing_time.total_seconds() - 3600)
        else:
            queuing_times.append(queuing_time.total_seconds())

    return queuing_times
