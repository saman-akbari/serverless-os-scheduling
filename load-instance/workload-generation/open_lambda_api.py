import json
import logging
import os

import requests
from helper.common import init_logging

logger = logging.getLogger(__name__)
init_logging()

IP = os.environ["OL_IP"] if "OL_IP" in os.environ else "localhost"
PORT = 5000

"""
Check if OpenLambda is running
"""


def is_running() -> bool:
    try:
        url = "http://{}:{}/status".format(IP, PORT)
        logger.info(f"HTTP POST to {url}")
        response = requests.get(url)

        return response.status_code == 200 and response.text == "ready\n"
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to OpenLambda")
        return False


""" 
Run a function on OpenLambda
:param function_name: Name of the function to run
:param payload: Payload to send to the function
:param timeout: Timeout for the http connection in seconds
:param request_id: Optional index of the request for logging purposes
:return: The response from the OpenLambda function or None on error
"""


def run_function(
        function_name: str,
        payload: dict = None,
        request_id: int = None,
        deployment_id: int = None,
        timeout: int = 600,
) -> requests.Response | None:
    try:
        json_data = json.dumps(payload)
        url = "http://{}:{}/run/{}".format(IP, PORT, function_name)
        if request_id is not None:
            url += f"?id={request_id}"
        if deployment_id is not None:
            url += f"&dId={deployment_id}" if "?" in url else f"?dId={deployment_id}"

        logger.info(f"HTTP POST to {function_name} with {payload}")
        response = requests.post(url, data=json_data, timeout=timeout)

        # case: function_name doesnt exist at OL
        if response.status_code == 500 and response.text.find("lambda not found") != -1:
            logger.error(f"OpenLambda couldn't find {function_name}")
            return

        # handle successful request
        if response.status_code != 200:
            logger.error(
                f"OpenLambda returned {response.status_code} - {response.text}"
            )
            return

        return response

    # case: OL instance is not running
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to OpenLambda")
        return None
