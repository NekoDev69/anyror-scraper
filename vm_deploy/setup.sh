#!/bin/bash
# VM Setup Script for AnyROR Bulk Scraper
# Run this on a fresh Ubuntu/Debian VM

set -e

echo "=========================================="
echo "AnyROR Bulk Scraper - VM Setup"
echo "=========================================="

# Update system
echo "📦 Updating system..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git

# Create project directory
echo "📁 Setting up project..."
mkdir -p ~/anyror-scraper
cd ~/anyror-scraper

# Create virtual environment
echo "🐍 Creating Python environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing Python packages..."
pip install --upgrade pip
pip install playwright google-genai fastapi uvicorn python-multipart

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium
playwright install-deps chromium

# Create output directories
echo "📂 Creating output directories..."
mkdir -p output/{raw,structured,reports,screenshots,debug,jobs}

echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo "=========================================="
echo ""
echo "To start the API server:"
echo "  cd ~/anyror-scraper"
echo "  source venv/bin/activate"
echo "  python vm_api.py"
echo ""
echo "API will be available at http://<vm-ip>:8000"
echo ""
