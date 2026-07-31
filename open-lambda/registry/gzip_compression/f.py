"""
This code was retrieved on 2024-10-10 and adapted from:
Jeongchul Kim and Kyungyong Lee, 'Function Bench : A Suite of Workloads for Serverless Cloud Function Service', IEEE International Conference on Cloud Computing 2019, 07/2019
"""

import gzip
import os
from time import time
from uuid import uuid4


def f(event):
    timestamps = {}
    timestamps["starting_time"] = time()

    file_size = event["file_size"]
    source_id = uuid4()
    target_id = uuid4()
    file_write_path = f"/tmp/{source_id}"
    file_target_path = f"/tmp/{target_id}"
    num_of_iterations = event[
        "num_of_iterations"
    ]  # if event["num_of_iterations"] != 0 else 1

    # create source file
    create_source_start = time()
    with open(file_write_path, "wb") as file:
        file.write(os.urandom(file_size * 1024))  # * 1024))
    disk_latency = time() - create_source_start

    # gzip source file
    with open(file_write_path, "rb") as file:
        gzip_start = time()
        for _ in range(num_of_iterations):
            file.seek(0)
            with gzip.open(file_target_path, "wb") as gz:
                gz.writelines(file)
        end = time()
        compress_latency = end - gzip_start

    os.remove(file_write_path)
    if num_of_iterations != 0:
        os.remove(file_target_path)

    timestamps["finishing_time"] = time()
    latency = timestamps["finishing_time"] - timestamps["starting_time"]
    return {
        "latency": latency,
        "disk_write": disk_latency,
        "compress": compress_latency,
        "timestamps": timestamps,
    }
