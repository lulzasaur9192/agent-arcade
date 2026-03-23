#!/bin/bash
cd "$(dirname "$0")"

echo "Installing Python dependencies..."
python3 -m pip install -q -r requirements.txt

# Remove old DB for fresh start
rm -f agent_arcade.db test_arcade.db

echo ""
echo "Starting Agent Arcade API server..."
echo "Server: http://localhost:5000"
echo "API:    http://localhost:5000/api/games"
echo ""
python3 app.py
