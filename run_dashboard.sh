#!/bin/bash
# Run AnyROR Dashboard locally

echo "🚀 Starting AnyROR Dashboard..."
echo "   Open http://localhost:8080 in your browser"
echo ""

# Install deps if needed
pip3 install fastapi uvicorn pydantic --quiet 2>/dev/null

# Run
python3 -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080 --reload
