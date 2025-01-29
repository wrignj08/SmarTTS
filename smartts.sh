#!/bin/bash

# Name of the conda environment
CONDA_ENV_NAME="TTS"

# Path to your python script
PYTHON_SCRIPT="smartts.py"

# Process command line arguments
VERBOSE_FLAG=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE_FLAG="--verbose"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Activate the conda environment
eval "$(conda shell.bash hook)"
conda activate $CONDA_ENV_NAME

# Run the Python script with optional verbose flag
python $PYTHON_SCRIPT $VERBOSE_FLAG

# Deactivate the conda environment
conda deactivate