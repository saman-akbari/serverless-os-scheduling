"""
This code was retrieved on 2024-10-10 and adapted from:
Jeongchul Kim and Kyungyong Lee, 'Function Bench : A Suite of Workloads for Serverless Cloud Function Service', IEEE International Conference on Cloud Computing 2019, 07/2019
"""

from time import time

from numpy import matrix, linalg, random


def linpack(n, iterations):
    # LINPACK benchmarks
    # ops = (2.0 * n) * n * n / 3.0 + (2.0 * n) * n

    # Create AxA array of random numbers -0.5 to 0.5
    A = random.random_sample((n, n)) - 0.5
    B = A.sum(axis=1)

    # Convert to matrices
    A = matrix(A)
    B = matrix(B.reshape((n, 1)))

    # Ax = B
    for _ in range(iterations):
        x = linalg.solve(A, B)


def f(event):
    timestamps = {}
    timestamps["starting_time"] = time()

    n = int(event["n"])
    metadata = event["metadata"]
    iterations = event["num_of_iterations"]  # if event["num_of_iterations"] != 0 else 1
    linpack(n, iterations)

    timestamps["finishing_time"] = time()
    latency = timestamps["finishing_time"] - timestamps["starting_time"]
    return {"latency": latency, "timestamps": timestamps, "metadata": metadata}
