#!/bin/bash
# Script to run the FastAPI backend server

# Activate virtual environment
source .venv/bin/activate

# Run FastAPI in development mode
python -m fastapi dev main.py --port 8000
