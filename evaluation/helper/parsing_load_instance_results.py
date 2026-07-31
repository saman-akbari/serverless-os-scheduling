from pathlib import Path

import pandas as pd
from .parsing_plan import get_plan_ids
from .parsing_sched_order import get_sched_command_order, get_sched_cmd_idx


def get_plan_id_from_result_path(p: Path) -> str:
    """Determines the associated plan_id for a given measurement result path of the load instance"""
    return p.stem.split("_")[-1]


def get_sorted_result_paths(root: Path) -> list[Path]:
    """Returns a sorted list of paths of all measurement results of the load-instance"""
    results_path = root / "results"
    results = sorted(list(results_path.iterdir()))
    # assert
    sched_order = get_sched_command_order(root)
    assert (
            len(results) % len(sched_order) == 0
    ), "results count doesnt match sched count in sched-order.txt"
    return results


def get_result_paths(root: Path, plan_id: int) -> list[Path]:
    """Get paths to all measurement results of the load-instance associated with a given plan_id"""
    result_paths = get_sorted_result_paths(root)
    plan_ids = get_plan_ids(root)
    sched_cmds = get_sched_command_order(root)
    # ensure that we have expected total number of result_paths
    expected = len(plan_ids) * len(sched_cmds)
    actual = len(result_paths)
    assert (
            expected == actual
    ), f"Expected {expected} result files in total. Got: {actual}"
    # ensure that each plan has one result per scheduler
    arr = [get_plan_id_from_result_path(result_path) for result_path in result_paths]
    for p_id in plan_ids:
        expected = len(sched_cmds)
        actual = arr.count(p_id)
        assert (
                expected == actual
        ), f"Expected {expected} result files for plan_id={p_id}. Got: {actual}"
    # filter by plan_id
    return list(filter(lambda p: get_plan_id_from_result_path(p) == str(plan_id), result_paths))


def get_result_path(root: Path, plan_id: int, sched_cmd: str) -> Path:
    """Get the load-instance's measurement result path for a given (plan_id, sched_cmd)"""
    result_paths = get_result_paths(root, plan_id)
    idx = get_sched_cmd_idx(root, sched_cmd)
    return result_paths[idx]


def get_result_data(root: Path, plan_id: int, sched_cmd: str) -> pd.DataFrame:
    """Returns the measurement results of the load instance for a given plan_id, sched_cmd combination"""
    result_path = get_result_path(root, plan_id, sched_cmd)
    return pd.read_csv(result_path)
