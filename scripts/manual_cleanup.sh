#!/bin/bash
source ./scripts/common.sh
source ./scripts/measurement.sh

assertCorrectArgNumber $# 1

sudo pkill -f track-system-ctxt-switches.sh 2>/dev/null || true
sudo pkill -f mpstat 2>/dev/null || true

rm ./load-instance/data/AzureFunctionsInvocationTraceForTwoWeeksJan2021.txt
rm -rfd ./load-instance/workload-generation/plans
rm -rfd ./load-instance/workload-generation/samples
rm -rfd ./load-instance/workload-generation/results
rm ./open-lambda/scx.log
rm ./open-lambda/mpstat.log
rm ./open-lambda/system-ctxt.logs
rm ./open-lambda/lscpu.log

cd open-lambda || exit 1
./cleanup.sh "$1"
