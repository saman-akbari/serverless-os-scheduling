#!/bin/bash
# parse arguments
if [ "$#" -ne 2 ]; then
	echo "ERROR: missing scheduler argument"
	echo "Usage: $0 plan-id scaling"
	echo "   executes plan with given plan-id"
	echo "   IAT are multiplied with scaling parameter"
	exit 1
fi

# fetch openlambda_instance internal ip or set to localhost
OL_IP=$(curl -s -H "Metadata-Flavor: Google" \
	"http://metadata.google.internal/computeMetadata/v1/instance/attributes/ol-ip")

if [ -z "$OL_IP" ]; then
	OL_IP="localhost"
fi

source .env/bin/activate
cd ./workload-generation || exit 1

OL_IP=$OL_IP python ./execute_plan.py --plan-id "$1" --scaling "$2"
