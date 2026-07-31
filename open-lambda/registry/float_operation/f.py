"""
This code was retrieved on 2024-10-10 and adapted from:
Jeongchul Kim and Kyungyong Lee, 'Function Bench : A Suite of Workloads for Serverless Cloud Function Service', IEEE International Conference on Cloud Computing 2019, 07/2019
"""

import math
from time import time


def float_operations(n):
    for i in range(0, n):
        sin_i = math.sin(i)
        cos_i = math.cos(i)
        sqrt_i = math.sqrt(i)


def f(event):
    timestamps = {}
    timestamps["starting_time"] = time()

    n = int(event["n"]) + 7000
    metadata = event["metadata"]
    float_operations(n)

    timestamps["finishing_time"] = time()
    latency = timestamps["finishing_time"] - timestamps["starting_time"]
    return {"latency": latency, "timestamps": timestamps, "metadata": metadata}
