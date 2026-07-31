import re
from pathlib import Path

import pandas as pd


def get_plan_paths(root: Path, with_plans_subdir=True):
    """Gets all plan paths of a given measurement"""

    plans_path = root
    if with_plans_subdir:
        plans_path = root / "plans"

    results = []
    for p in plans_path.iterdir():
        if p.is_file() and re.search("^plan\\d+\\.csv$", p.name):
            results.append(p)
    return results


def get_plan_ids(root: Path, with_plans_subdir=True):
    """Determines the plan_ids of a given measurement"""
    paths = get_plan_paths(root, with_plans_subdir)
    return list(sorted(map(lambda p: p.stem[-1], paths)))


def get_plan(root: Path, plan_id: int, with_plans_subdir=True) -> pd.DataFrame:
    """Returns the data of a plan associated with a given plan_id"""

    plan_path = root
    if with_plans_subdir:
        plan_path /= "plans"

    plan_path /= f"plan{plan_id}.csv"

    return pd.read_csv(
        plan_path, header=None, names=["iat", "dId", "duration", "functionName", "n"]
    )
