import logging

import pandas as pd

AZURE_DATASET_PATH = "../data/AzureFunctionsInvocationTraceForTwoWeeksJan2021.txt"

CONFIG = {
    "float_operation": {
        "parameterName": "n",
        "jsonPayload": {"metadata": {}},
    },
    "linpack": {
        "parameterName": "num_of_iterations",
        "jsonPayload": {"n": "200", "metadata": {}},
    },
    "matmul": {
        "parameterName": "num_of_iterations",
        "jsonPayload": {"n": 100, "metadata": {}},
    },
    "pyaes": {
        "parameterName": "num_of_iterations",
        "jsonPayload": {"length_of_message": 100, "metadata": {}},
    },
    "chameleon": {
        "parameterName": "num_of_iterations",
        "jsonPayload": {"num_of_rows": 100, "num_of_cols": 100, "metadata": {}},
    },
    "gzip_compression": {
        "parameterName": "num_of_iterations",
        "jsonPayload": {"file_size": 10},
    },
}


def load_azure_dataset(path=AZURE_DATASET_PATH):
    """
    Load azure function invocation dataset, and extend with start_timestamp col
    """
    df = pd.read_csv(path)
    # remove function traces with zero duration
    df = df[df["duration"] > 0]

    df = df.copy()
    df.loc[:, "start_timestamp"] = df["end_timestamp"] - df["duration"]
    df.sort_values(by=["start_timestamp"], inplace=True)
    return df


def load_azure_sample(path: str):
    df = pd.read_csv(path)

    # remove function traces with zero duration
    df = df[df["duration"] > 0]
    df.rename(columns={"start_timestamp": "iat"}, inplace=True)

    return df


def init_logging():
    logging.basicConfig(
        format="{asctime}.{msecs:03.0f} - {name} - {levelname} - {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )


def parse_response(function_name: str, response) -> tuple[float, dict[str, float]]:
    """
    Parse the response from OpenLambda function call
    :param function_name: The name of the function being called
    :param response: The response object from requests library
    returns: latency and timestamps returned by OL function or None
    """
    assert (
            function_name in CONFIG.keys()
    ), f"Unknown function_name at parse_response: {function_name}"

    results = response.json()
    latency = results["latency"]
    timestamps = {
        "starting_time": results["timestamps"]["starting_time"],
        "finishing_time": results["timestamps"]["finishing_time"],
    }
    return latency, timestamps
