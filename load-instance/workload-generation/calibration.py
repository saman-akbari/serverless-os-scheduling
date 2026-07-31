import argparse
import logging
import math
import statistics
from datetime import datetime
from typing import Callable

from scipy import stats

import matplotlib.pyplot as plt
import numpy as np
import open_lambda_api
from helper.common import load_azure_dataset, init_logging, CONFIG, parse_response

logger = logging.getLogger(__name__)
init_logging()

NUM_INPUTS_DEFAULT = 21
ITERATIONS_DEFAULT = 2
TARGET_EXECUTION_DURATION_DEFAULT = 10  # seconds
MAX_TRIES_BINARY_SEARCH_DEFAULT = 3


def call_function(function_name, payload) -> float | None:
    """
    Calls the OpenLambda function and parses the response
    :param function_name: The name of the function to call
    :param payload: The payload to send to the function
    returns: The latency of the function call
    """
    response = open_lambda_api.run_function(function_name, payload)

    if response is None:
        logger.warning(f"OpenLambda function call for {function_name} failed")
        return None

    # parse response
    latency, timestamps = parse_response(function_name, response)

    if (
            latency is None
            or timestamps is None
            or "starting_time" not in timestamps
            or "finishing_time" not in timestamps
            or timestamps["starting_time"] is None
            or timestamps["finishing_time"] is None
    ):
        logger.warning(f"Unknown function_name at call_function: {function_name}")
        return None

    return latency


def _prepare(function_name):
    """
    Prepare the environment for calibration

    Some functions depend on external packages, 
    External packages may be installed during first call
    This can increase the startup time.
    This function ensures that all necessary packages are installed.
    """
    logger.info("Preparing calibration")
    parameter_name = CONFIG[function_name]["parameterName"]
    payload = CONFIG[function_name]["jsonPayload"].copy()
    payload[parameter_name] = 1

    open_lambda_api.run_function(function_name, payload)


def exponential_probing(
        function_name: str, parameter_name: str, execution_duration: int, json_payload: dict
):
    """
    Exponential probing to find the upper bound of a parameter for a given function
    :param function_name: The name of the function to test
    :param parameter_name: The name of the parameter to vary
    :param execution_duration: The target execution duration in seconds
    :param json_payload: Other static data to send to function call
    returns: The upper bound of the parameter value search space
    """
    logger.info(f"Starting exponential probing for {function_name}")
    base = 2
    exponent = 0
    while True:
        parameter_value = base ** exponent

        json_payload[parameter_name] = parameter_value
        latency = call_function(function_name, json_payload)

        if latency is None:
            raise Exception("ERROR: Failed to call OL function. Is OpenLambda online?")

        if latency >= execution_duration:
            logger.info(
                f"Exponential probing found upper bound: {parameter_name}={parameter_value} with {latency}s"
            )
            return parameter_value

        exponent += 1


def binary_search(
        function_name: str,
        parameter_name: str,
        target_execution_duration: int,
        json_payload: dict,
        upper_bound: int,
        absolute_error: int = 1,
):
    """
    Binary Search adapted to find parameter n which executes for execution_duration +/- absolute_error
    :param function_name: The name of the function to test
    :param parameter_name: The name of the parameter to vary
    :param target_execution_duration: The target execution duration in seconds
    :param json_payload: Other static data to send to function call
    :param upper_bound: The upper bound of the parameter value search space
    :param absolute_error: The error margin for the target execution duration
    returns: The input parameter value that achieves the target execution duration
    """
    left = 0
    right = upper_bound
    while left <= right:
        current_parameter_value = left + math.floor((right - left) / 2)

        json_payload[parameter_name] = current_parameter_value

        latency = call_function(function_name, json_payload)

        if latency < target_execution_duration - absolute_error:
            left = current_parameter_value + 1
        elif latency > target_execution_duration + absolute_error:
            right = current_parameter_value - 1
        else:
            logger.info(
                f"Binary search found for {function_name}({parameter_name}={current_parameter_value}) execution of {latency}sec"
            )
            return current_parameter_value

    logger.error(f"Binary search failed for {function_name}({parameter_name})")
    return


def find_input_parameter(
        function_name: str,
        parameter_name: str,
        execution_duration: int,
        json_payload: dict,
        max_attempts: int = MAX_TRIES_BINARY_SEARCH_DEFAULT,
):
    """
    Determine function input parameter of given function s.t. function_name(n) executes for d_exec +/- 5s
    :param function_name: The name of the function to test
    :param parameter_name: The name of the parameter to vary
    :param execution_duration: The target execution duration in seconds
    :param json_payload: Other static data to send to function call
    :param max_attempts: The maximum number of attempts to repeat binary search in case search fails
    returns: The input parameter value that achieves the target execution duration
    """
    # find first parameter with execution duration >= d_exec
    upper_bound = exponential_probing(
        function_name, parameter_name, execution_duration, json_payload
    )

    # find n s.t. f(n) executes d_exec
    for try_index in range(max_attempts):
        logger.info(
            f"Binary search try {try_index + 1}/{max_attempts} for {function_name}({parameter_name})"
        )
        parameter_value = binary_search(
            function_name, parameter_name, execution_duration, json_payload, upper_bound
        )
        if parameter_value is not None:
            return parameter_value

    raise Exception(
        f"Failed to find input parameter for {function_name} after {max_attempts} tries"
    )


def gather_data(
        function_name,
        parameter_name,
        payload,
        iterations=ITERATIONS_DEFAULT,
        num_inputs=NUM_INPUTS_DEFAULT,
        max_attempts=MAX_TRIES_BINARY_SEARCH_DEFAULT,
        target_exec_duration=TARGET_EXECUTION_DURATION_DEFAULT,
):
    """
    Gather execution durations for the given serverless function within log spaced [0, target_exec_duration]
    :param function_name: The name of the function to test
    :param parameter_name: The name of the parameter to vary
    :param payload: The payload to send with the function call
    :param iterations: The number of measurements to perform for each input size to determine average execution duration
    :param num_inputs: The number of input sizes to test - logarithmically spaced within [0, target_exec_duration]
    :param max_attempts: The maximum number of attempts to repeat binary search in case search fails
    :param target_exec_duration: The maximum target execution duration in seconds
    :returns a tuple of (list of input sizes, list of execution durations)
    """
    _prepare(function_name)

    stop = find_input_parameter(
        function_name, parameter_name, target_exec_duration, payload.copy(), max_attempts
    )

    logger.info(f"Creating log input sample to train model for {function_name}")
    ns = list(
        map(
            round,
            np.logspace(
                0, math.floor(math.log(stop, 2)), num_inputs, endpoint=True, base=2
            ),
        )
    )

    parameter_latencies = {n: [] for n in ns}
    for n in ns:
        for _ in range(iterations):
            logger.info(f"Gathering calibration data for {parameter_name}={n}")
            current_payload = payload.copy()
            current_payload[parameter_name] = n
            latency = call_function(function_name, current_payload)
            parameter_latencies[n].append(latency)

    ns = sorted(parameter_latencies.keys())
    means = [statistics.mean(parameter_latencies[n]) for n in ns]

    return ns, means


def build_model(ns, exec_durations):
    """
    Build linear regression model and its inverse from gathered data
    :param ns: The input sizes used for gathering data
    :param exec_durations: The corresponding execution durations for each input size
    :returns: A tuple containing the inverse function and the linear regression model
    """
    logger.info("Building model")
    m, b, r, p, std_error = stats.linregress(ns, exec_durations)

    logger.info(f"Linear Regression returned m={m} b={b} r={r}")

    if r < 0.6:
        logger.error(f"The correlation coefficient is too low: r={r}")
        exit(1)

    # exec_duration -> n
    def inverse_f(y):
        if y < 0:
            logger.error("execution duration must be >= 0")
            exit(1)
        if y == 0:
            return round(b)

        res = (y - b) / m
        return round(res) if res > 0 else 0

    # n -> exec duration
    def f(x):
        y = m * x + b
        return y if y > 0 else 0

    return inverse_f, f


def calibrate(
        iterations: int = ITERATIONS_DEFAULT,
        num_inputs: int = NUM_INPUTS_DEFAULT,
        max_attempts: int = MAX_TRIES_BINARY_SEARCH_DEFAULT,
        target_exec_duration: int = TARGET_EXECUTION_DURATION_DEFAULT,
) -> dict[str, Callable]:
    """
    Calibrate all functions defined in CONFIG
    :param iterations: The number of measurements for each input size to determine average execution duration
    :param num_inputs: The number of input sizes to test - logarithmically spaced within [0, target_exec_duration]
    :param max_attempts: The maximum number of attempts to repeat binary search in case search fails
    :param target_exec_duration: The maximum target execution duration in seconds
    :return: A dictionary mapping function names to their inverse models
    """
    models = {}

    for function_name in CONFIG.keys():
        parameter_name = CONFIG[function_name]["parameterName"]
        payload = CONFIG[function_name]["jsonPayload"].copy()

        ns, exec_durations = gather_data(
            function_name,
            parameter_name,
            payload,
            iterations,
            num_inputs,
            max_attempts,
            target_exec_duration,
        )

        inverse_f, _ = build_model(ns, exec_durations)
        models[function_name] = inverse_f

    return models


def _plot_linear_regression_results(
        function_name, parameter_name, ns, exec_durations, lin_reg_model
):
    """
    Plot linear regression model with it's training data
    """
    plt.figure()
    plt.scatter(ns, exec_durations, label="Actual Measurements", marker="x", color="g")

    model_results = list(map(lin_reg_model, ns))
    plt.plot(ns, model_results, label="Linear Regression")
    plt.xlabel(f"Input ({parameter_name})")
    plt.ylabel("Average Execution Duration (s)")
    plt.title(f"Model for {function_name} with its calibration data")
    plt.legend()
    plt.tight_layout()

    plt.savefig(f"../results/plots/{datetime.now()}_lin-reg-model_{function_name}.svg")
    plt.show()


if __name__ == "__main__":
    # cli parsing
    parser = argparse.ArgumentParser(
        description="Calibrate functions, validate their performance and visualize results"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=ITERATIONS_DEFAULT,
        help="The number of measurements for each input size to determine average execution duration",
    )
    parser.add_argument(
        "--num-inputs",
        type=int,
        default=NUM_INPUTS_DEFAULT,
        help="The number of inputs to gather - logarithmically spaced within [0, target_exec_duration]",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_TRIES_BINARY_SEARCH_DEFAULT,
        help="Number of binary search attempts to find the function input that results in targetExecutionDuration",
    )
    parser.add_argument(
        "--target-exec-duration",
        type=int,
        default=TARGET_EXECUTION_DURATION_DEFAULT,
        help="The maximum target execution duration in seconds to consider when gathering data for model training",
    )
    args = parser.parse_args()
    iterations = args.iterations
    num_inputs = args.num_inputs
    max_attempts = args.max_attempts
    target_exec_duration = args.target_exec_duration

    # For each function, load dataset, train model and validate model predictions
    for function_name in CONFIG.keys():
        parameter_name = CONFIG[function_name]["parameterName"]

        df = load_azure_dataset()

        ns, exec_durations = gather_data(
            function_name,
            parameter_name,
            CONFIG[function_name]["jsonPayload"].copy(),
            num_inputs=num_inputs,
            iterations=iterations,
            max_attempts=max_attempts,
            target_exec_duration=target_exec_duration,
        )

        inverse_f, lin_reg_model = build_model(ns, exec_durations)

        # Validation:
        # sample execution Durations [s]
        goal_durations = [0, 0.0001, 0.001, 0.01, 0.1, 1, 2, 5]

        # calculate corresponding ns with inverse
        calculated_n = list(map(inverse_f, goal_durations))

        # determine actual execution duration from predicted n
        latencies = []
        for i, n in enumerate(calculated_n):
            logger.info(
                f"Determine actual execution duration for f-1({goal_durations[i]}s)={n}"
            )

            current_payload = CONFIG[function_name]["jsonPayload"].copy()
            current_payload[parameter_name] = n
            latency = call_function(function_name, current_payload)
            latencies.append(latency)

        # determine errors
        filtered_indices = [
            i for i in range(len(latencies)) if latencies[i] is not None
        ]
        goal_durations = [goal_durations[i] for i in filtered_indices]
        latencies = [latencies[i] for i in filtered_indices]
        abs_deltas = [
            abs(goal_durations[i] - actual_exec_duration)
            for i, actual_exec_duration in enumerate(latencies)
        ]
        rel_deltas = [
            (
                abs(goal_durations[i] - actual_exec_duration) / goal_durations[i] * 100
                if goal_durations[i] != 0
                else actual_exec_duration * 100
            )
            for i, actual_exec_duration in enumerate(latencies)
        ]

        # print results as table
        print(f"Validation results for {function_name}:")
        for i, t in enumerate(goal_durations):
            print(
                f"{t:7.4f} | {calculated_n[i]:010} | {latencies[i]:15.10f} | {abs_deltas[i]:15.10f} | {rel_deltas[i]:15.10f}%"
            )

        # plot linear regression model with it's training data
        _plot_linear_regression_results(
            function_name, parameter_name, ns, exec_durations, lin_reg_model
        )
