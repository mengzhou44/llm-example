#!/bin/bash
cd "$(dirname "$0")"
python3.11 -m uvicorn main:app --reload --port 5001
