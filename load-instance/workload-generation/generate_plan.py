import argparse
import logging
import random
import time
from pathlib import Path
from typing import Callable

import calibration
import pandas as pd
from helper.common import load_azure_dataset, init_logging, load_azure_sample

init_logging()

logger = logging.getLogger(__name__)

NUM_PLANS_DEFAULT = 3
PLANS_DIRECTORY_DEFAULT = "plans"
SAMPLE_DIRECTORY_DEFAULT = "samples"
DURATION_DEFAULT = 10  # minutes
SAMPLE_SIZE_DEFAULT = 600


def assign_function_names(df: pd.DataFrame, function_names: list[str]) -> pd.DataFrame:
    """
    Assigns new columns to df with functions names. 

    Function names are assigned via modulo
    """
    df["id"] = df["app"] + df["func"]
    function_ids = df["id"].unique()

    total_functions = len(function_names)
    function_name_map = {
        function_id: function_names[index % total_functions]
        for (index, function_id) in enumerate(function_ids)
    }

    df["function_name"] = df["id"].map(function_name_map)
    df.drop(columns=["id"], inplace=True)

    return df


def generate_plan_from_sample(
        sample_index: int,
        sample: pd.DataFrame,
        models: dict[str, Callable[[float], int]],
        out_dir: str = PLANS_DIRECTORY_DEFAULT,
):
    assign_function_names(sample, list(sorted(models.keys())))

    plan_df = sample.loc[:, ["iat", "duration", "function_name", "app", "func"]]

    # generate numeric function deployment ids
    plan_df["id"] = plan_df["app"] + plan_df["func"]
    deployment_to_id = {
        deployment: id for id, deployment in enumerate(plan_df["id"].unique())
    }
    plan_df.replace(deployment_to_id, inplace=True)
    plan_df.drop("app", axis=1, inplace=True)
    plan_df.drop("func", axis=1, inplace=True)

    # predict for each request the input parameter based on previous model
    for index, row in plan_df.iterrows():
        function_name = row["function_name"]
        exec_duration = row["duration"]

        # local restriction:
        if exec_duration > 120:
            exec_duration = 120

        model = models[function_name]
        plan_df.at[index, "n"] = int(model(exec_duration))

    plan_df["n"] = plan_df["n"].astype(int)  # to store inputs as actual ints

    # store plan
    output_root_dir = Path(out_dir)
    if not output_root_dir.exists():
        output_root_dir.mkdir()
        logger.info(f"{output_root_dir} directory created")

    plan_filepath = output_root_dir / f"plan{sample_index}.csv"
    plan_df.to_csv(
        plan_filepath.absolute(),
        columns=["iat", "id", "duration", "function_name", "n"],
        index=False,
        header=False,
    )
    logger.info(f"Plan written to {plan_filepath.absolute()}")


def does_overlap_exist(
        plans: list[tuple[float, float]], new_t0: float, new_t1: float
) -> bool:
    """
    Check if the timespan of new_plan overlaps with any existing plans
    :param plans: List of start and end timestamps in 2w period of existing plans as tuples of (start, end)
    returns true if there is an overlap, otherwise false

    Assumption: each plan in plans and new_plan have the same duration
    """
    for current_plan in plans:
        t0 = current_plan[0]
        t1 = current_plan[1]

        if not (new_t1 < t0 or new_t0 > t1):
            return True
    return False


def set_seed(seed: int, store_plan: bool = False, out_dir: str = PLANS_DIRECTORY_DEFAULT):
    """
    Fixes randomness to make results reproducible and optionally stores it in the plans directory
    :param seed: The seed value to set
    """
    random.seed(seed)

    if store_plan is False:
        return

    output_root_dir = Path(out_dir)
    if not output_root_dir.exists():
        output_root_dir.mkdir()
        logger.info(f"{output_root_dir} directory created")

    seed_path = Path(out_dir) / "seed.txt"
    with open(seed_path.absolute(), "w") as f:
        f.write(str(seed))
        logger.info(f"Seed saved to {seed_path.absolute()}")


def clean_up(
        plan_dir: str = PLANS_DIRECTORY_DEFAULT, sample_dir: str = SAMPLE_DIRECTORY_DEFAULT
):
    """
    Delete plan root directory if exists on startup
    """
    plan_out_dir = Path(plan_dir)
    sample_out_dir = Path(sample_dir)

    if plan_out_dir.exists():
        remove_dir_recursively(plan_out_dir)

    if sample_out_dir.exists():
        remove_dir_recursively(sample_out_dir)


def remove_dir_recursively(dir: Path):
    for nodes in dir.iterdir():
        if nodes.is_file():
            nodes.unlink()
            logger.info(f"{nodes} deleted")
            continue
        elif nodes.is_dir():
            logger.warning(f"Found unexpected directory {nodes} => skipping")
            continue
        else:
            logger.warning(f"Found unexpected node {nodes} => skipping")
            continue
    dir.rmdir()
    logger.info(f"Directory {dir} deleted")


# random sampling => pick n random requests
# (each request has equal chance of getting selected)
def get_random_sample(df: pd.DataFrame, frac: float, random_seed: int) -> pd.DataFrame:
    return df.sample(frac=frac, random_state=random_seed)


def generate_samples(
        number_samples: int,
        number_requests: int,
        duration: float,
        random_seed: int,
        out_dir: str,
):
    """
    Generate samples from with given samplesize and duration [min]
    """
    original = load_azure_dataset(
        "../data/AzureFunctionsInvocationTraceForTwoWeeksJan2021.txt"
    )
    scaling_factor = 1 / (14 * 24 * (60 / duration))
    frac = number_requests / original.shape[0]

    # create sample dir
    sample_path = Path(out_dir)

    if not sample_path.exists():
        sample_path.mkdir()

    sample_paths = []
    for index in range(number_samples):
        sample = get_random_sample(original, frac, random_seed + index)
        sample = sample.copy()
        sample.loc[:, "start_timestamp"] = sample["start_timestamp"] * scaling_factor
        sample.sort_values(by=["start_timestamp"], inplace=True)

        out_target = Path(out_dir) / f"sample{index}.csv"

        sample.to_csv(
            out_target,
            index=False,
            columns=["app", "func", "start_timestamp", "duration"],
        )
        sample_paths.append(out_target)
    return sample_paths


if __name__ == "__main__":
    # cli parsing
    SEED_DEFAULT = int(time.time())
    parser = argparse.ArgumentParser(
        description="Generate workload plans for execute_plan.py"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED_DEFAULT,
        help="Set seed to make results reproducible",
    )
    parser.add_argument(
        "--num-plans",
        type=int,
        default=NUM_PLANS_DEFAULT,
        help="Number of plans to generate. Creates also n random samples from first Day of Azrue Dataset",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=PLANS_DIRECTORY_DEFAULT,
        help="Directory to store plans",
    )
    parser.add_argument(
        "--sample-out",
        type=str,
        default=SAMPLE_DIRECTORY_DEFAULT,
        help="Directory to store random samples",
    )
    parser.add_argument(
        "--num-requests",
        type=int,
        default=SAMPLE_SIZE_DEFAULT,
        help="Sample size of random sampling from first day of azure day",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DURATION_DEFAULT,
        help="Target duration of sample [min]",
    )
    args = parser.parse_args()
    num_plans = args.num_plans
    seed = args.seed
    plans_out_dir = args.out
    samples_out_dir = args.sample_out
    sample_path = args.sample_out
    sample_size = args.num_requests
    duration = args.duration

    # remove old plans
    clean_up(plans_out_dir)

    # make results reproducible
    set_seed(seed, True, plans_out_dir)

    # generate n random samples
    sample_paths = generate_samples(num_plans, sample_size, duration, seed, samples_out_dir)

    # calibrate prediction models
    models = calibration.calibrate()

    for sample_index, sample_path in enumerate(sample_paths):
        # generate workload plans
        azure_function_traces = load_azure_sample(sample_path)

        generate_plan_from_sample(sample_index, azure_function_traces, models, plans_out_dir)
