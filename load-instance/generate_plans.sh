#!/bin/bash
if [ "$#" -ne 3 ]; then
	echo "ERROR: Wrong program usage"
	echo ""
	echo "Usage: $0 n sample-size scaling-factor"
	echo "   Generate n plans from n samples with sample-size & scaling factor"
	exit 1
fi
NUM_PLANS="$1"
SAMPLE_SIZE="$2"
DURATION="$3"

# fetch openlambda_instance internal ip or set to localhost
OL_IP=$(curl -s -H "Metadata-Flavor: Google" \
	"http://metadata.google.internal/computeMetadata/v1/instance/attributes/ol-ip")

if [ -z "$OL_IP" ]; then
	OL_IP="localhost"
fi

source .env/bin/activate
cd ./workload-generation || exit 1

OL_IP=$OL_IP python ./generate_plan.py --num-plans "$NUM_PLANS" --num-requests "$SAMPLE_SIZE" --duration "$DURATION"

if [ $? -ne 0 ]; then
	echo "ERROR: Plan generation failed."
	exit 1
fi
