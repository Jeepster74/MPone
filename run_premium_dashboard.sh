#!/bin/bash
echo "🏎️ Launching MP Intelligence Premium Dashboard..."
echo "------------------------------------------------"
echo "Step 1: Building Docker containers (Handling Node.js/React internally)..."

cd premium-dashboard
docker-compose up --build -d

echo "------------------------------------------------"
echo "✅ Dashboard is now LIVE!"
echo "Access URL: http://localhost:8000"
echo "Default User: jaap"
echo "Default Password: admin123"
echo "------------------------------------------------"
echo "Note: The background enrichment script is still running safely in the background."
