"""
This code was retrieved on 2024-10-10 and adapted from:
Jeongchul Kim and Kyungyong Lee, 'Function Bench : A Suite of Workloads for Serverless Cloud Function Service', IEEE International Conference on Cloud Computing 2019, 07/2019
"""

import random
import string
from time import time

import pyaes


def generate(length):
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for i in range(length))


def f(event):
    timestamps = {}
    timestamps["starting_time"] = time()

    length_of_message = event["length_of_message"]
    num_of_iterations = event[
        "num_of_iterations"
    ]  # if event['num_of_iterations'] != 0 else 1
    metadata = event["metadata"]

    message = generate(length_of_message)

    # 128-bit key (16 bytes)
    KEY = b"\xa1\xf6%\x8c\x87}_\xcd\x89dHE8\xbf\xc9,"

    for _ in range(num_of_iterations):
        aes = pyaes.AESModeOfOperationCTR(KEY)
        ciphertext = aes.encrypt(message)

        aes = pyaes.AESModeOfOperationCTR(KEY)
        plaintext = aes.decrypt(ciphertext)
        aes = None

    timestamps["finishing_time"] = time()
    latency = timestamps["finishing_time"] - timestamps["starting_time"]
    return {"latency": latency, "timestamps": timestamps, "metadata": metadata}
