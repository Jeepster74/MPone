#!/bin/bash

# Navigate to frontend directory
cd "premium-dashboard/frontend" || exit

# Check if node is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed or not in PATH."
    exit 1
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Build the frontend
echo "Building frontend..."
npm run build

# Check if build was successful
if [ -d "dist" ]; then
    echo "Build successful. Deploying to backend..."
    
    # Remove old static files from backend
    rm -rf ../static/*
    
    # Copy new build to backend static folder
    cp -r dist/* ../static/
    
    # Copy the PDF report to static as well
    cp "../../MP ONE Karting Venue Acquisition Strategy.pdf" "../static/"

    # Create the placeholder index.html again just in case? NO! We want the app.
    # But wait, if we overwrite static, we lose the PDF if we don't copy it again.
    # Added the cp for PDF above.
    
    echo "deployment complete!"
    echo "Please refresh your browser at http://localhost:8000"
else
    echo "Error: Build failed. 'dist' directory not found."
    exit 1
fi
