#!/bin/bash

# PenTest Master Device API Startup Script

echo "🛡️  Starting PenTest Master Device API..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
mkdir -p /tmp/downloads
mkdir -p /tmp/logs

# Start the FastAPI server
echo "Starting FastAPI server on http://0.0.0.0:8080"
echo "API Documentation: http://localhost:8080/docs"
echo "Control Panel: Open your index.html in browser"
echo ""
echo "Press Ctrl+C to stop the server"

uvicorn main:app --host 0.0.0.0 --port 8080 --reload --log-level info
