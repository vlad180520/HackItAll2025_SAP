#!/bin/bash
# Script to set up the Python virtual environment

# Remove old virtual environment if it exists
rm -rf .venv

# Create new virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

echo "✅ Virtual environment setup complete!"
echo "To activate: source .venv/bin/activate"
echo "To run server: python -m fastapi dev main.py --port 8000"
