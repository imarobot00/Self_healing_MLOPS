#!/bin/bash

# 🚀 Quick Start Script for AQI Prediction API
# ==============================================
# This script helps you get the API up and running quickly

set -e

echo "========================================"
echo "🚀 AQI Prediction API - Quick Start"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found"
    echo "💡 Please run this script from the api/ directory:"
    echo "   cd api && bash quickstart.sh"
    exit 1
fi

# Check Python version
echo "🔍 Checking Python version..."
python3 --version

# Check if required packages are installed
echo ""
echo "🔍 Checking dependencies..."
if python3 -c "import fastapi, uvicorn, dill, river" 2>/dev/null; then
    echo "✅ All required packages installed"
else
    echo "❌ Missing packages. Installing from requirements.txt..."
    pip install -r requirements.txt
fi

# Check if model exists
echo ""
echo "🔍 Checking for trained model..."
if [ -d "../training/models" ]; then
    MODEL_COUNT=$(ls ../training/models/arf_model_*.pkl 2>/dev/null | wc -l)
    if [ "$MODEL_COUNT" -gt 0 ]; then
        LATEST_MODEL=$(ls -t ../training/models/arf_model_*.pkl | head -1)
        echo "✅ Found model: $(basename $LATEST_MODEL)"
    else
        echo "❌ No trained models found in ../training/models/"
        echo "💡 Please train a model first:"
        echo "   cd ../training && python3 training.py"
        exit 1
    fi
else
    echo "❌ Models directory not found"
    exit 1
fi

# Check if port 8000 is available
echo ""
echo "🔍 Checking if port 8000 is available..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 8000 is already in use"
    echo "💡 Killing existing process..."
    PID=$(lsof -Pi :8000 -sTCP:LISTEN -t)
    kill -9 $PID 2>/dev/null || true
    sleep 2
fi

echo ""
echo "========================================"
echo "🚀 Starting FastAPI Server"
echo "========================================"
echo ""
echo "📍 Server will run on: http://localhost:8000"
echo "📚 Interactive docs: http://localhost:8000/docs"
echo "📖 Alternative docs: http://localhost:8000/redoc"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

# Start the server
python3 main.py
