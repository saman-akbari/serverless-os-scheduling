#!/bin/bash
sudo apt update
sudo apt install -y unrar python3-pip python3-venv

DATA_DIR="./data"
RAR_FILE="$DATA_DIR/AzureFunctionsInvocationTraceForTwoWeeksJan2021.rar"
TXT_FILE="$DATA_DIR/AzureFunctionsInvocationTraceForTwoWeeksJan2021.txt"

if [ -f "$TXT_FILE" ]; then
    echo "Azure trace data already extracted. Skipping."
elif [ -f "$RAR_FILE" ]; then
    echo "Extracting Azure trace data..."
    unrar x "$RAR_FILE" "$DATA_DIR/"
else
    echo "======================================================================"
    echo "ERROR: Azure dataset not found!"
    echo "Please download 'AzureFunctionsInvocationTraceForTwoWeeksJan2021.rar'"
    echo "from the official Azure Public Dataset repository and place it in:"
    echo "  $DATA_DIR/"
    echo ""
    echo "Reference: https://github.com/Azure/AzurePublicDataset"
    echo "======================================================================"
    exit 1
fi

echo "Setting up Python virtual environment in $(pwd)/.env ..."
python3 -m venv .env
source .env/bin/activate

echo "Installing Python dependencies..."
pip install -r ./workload-generation/requirements.txt

echo "Setup complete."
