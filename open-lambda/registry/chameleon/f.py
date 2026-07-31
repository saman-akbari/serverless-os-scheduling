"""
This code was retrieved on 2024-10-10 and adapted from:
Jeongchul Kim and Kyungyong Lee, 'Function Bench : A Suite of Workloads for Serverless Cloud Function Service', IEEE International Conference on Cloud Computing 2019, 07/2019
"""

from time import time

import six
from chameleon import PageTemplate

BIGTABLE_ZPT = """\
<table xmlns="http://www.w3.org/1999/xhtml"
xmlns:tal="http://xml.zope.org/namespaces/tal">
<tr tal:repeat="row python: options['table']">
<td tal:repeat="c python: row.values()">
<span tal:define="d python: c + 1"
tal:attributes="class python: 'column-' + %s(d)"
tal:content="python: d" />
</td>
</tr>
</table>""" % six.text_type.__name__


def f(event):
    timestamps = {}
    timestamps["starting_time"] = time()

    num_of_iterations = event["num_of_iterations"]
    num_of_rows = event["num_of_rows"]
    num_of_cols = event["num_of_cols"]
    metadata = event["metadata"]

    tmpl = PageTemplate(BIGTABLE_ZPT)
    for _ in range(num_of_iterations):
        data = {}
        for i in range(num_of_cols):
            data[str(i)] = i

        table = [data for x in range(num_of_rows)]
        options = {"table": table}

        data = tmpl.render(options=options)

    timestamps["finishing_time"] = time()
    latency = timestamps["finishing_time"] - timestamps["starting_time"]
    return {"latency": latency, "timestamps": timestamps, "metadata": metadata}
