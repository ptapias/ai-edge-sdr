#!/bin/bash
# Build script for LinkedIn AI SDR
# This script builds the frontend and copies it to the backend static folder

set -e

echo "Building LinkedIn AI SDR..."

# Build frontend
echo "Building frontend..."
cd frontend
npm install
npm run build

# Copy to backend static folder
echo "Copying frontend build to backend..."
mkdir -p ../backend/static
rm -rf ../backend/static/*
cp -r dist/* ../backend/static/

# Install backend dependencies
echo "Installing backend dependencies..."
cd ../backend
pip install -r requirements.txt

echo "Build complete!"
echo "Run with: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080"
