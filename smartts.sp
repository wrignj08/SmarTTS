#!/bin/bash

# Name of the conda environment
CONDA_ENV_NAME="TTS"

# Path to your python script
PYTHON_SCRIPT="smartts.py"

# Activate the conda environment
eval "$(conda shell.bash hook)"
conda activate $CONDA_ENV_NAME

# Run the Python script
python $PYTHON_SCRIPT

# Deactivate the conda environment
conda deactivate



