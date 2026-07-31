"""
This code was retrieved on 2024-10-10 and adapted from:
Jeongchul Kim and Kyungyong Lee, 'Function Bench : A Suite of Workloads for Serverless Cloud Function Service', IEEE International Conference on Cloud Computing 2019, 07/2019
"""

from time import time

import numpy as np


def matmul(n, iterations):
    A = np.random.rand(n, n)
    B = np.random.rand(n, n)

    for _ in range(iterations):
        C = np.matmul(A, B)


def f(event):
    timestamps = {}
    timestamps["starting_time"] = time()

    n = int(event["n"])
    iterations = event["num_of_iterations"]  # if event["num_of_iterations"] != 0 else 1
    metadata = event["metadata"]
    matmul(n, iterations)

    timestamps["finishing_time"] = time()
    latency = timestamps["finishing_time"] - timestamps["starting_time"]
    return {"latency": latency, "timestamps": timestamps, "metadata": metadata}
