#!/bin/bash
# Starts the FastAPI AI service on port 5001.
# Requires Python 3.11. For development hot-reload, add --reload.
cd "$(dirname "$0")"
python3.11 -m uvicorn main:app --port 5001
