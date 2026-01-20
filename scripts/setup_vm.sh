#!/bin/bash

# VM Environment Setup Script
# Installs dependencies and configures VM

# Usage: ./setup_vm.sh [VM_NAME]

set -e

VM_NAME=${1:-"scraper-turbo"}
ZONE="asia-south1-a"
PROJECT="anyror-scraper-2026"

echo "🔧 Setting up VM environment..."
echo "VM: $VM_NAME"
echo ""

gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command='
    cd ~/anyror-scraper
    
    echo "📦 Installing system dependencies..."
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-pip
    
    echo "📦 Creating virtual environment..."
    if [ ! -d "venv" ]; then
      python3 -m venv venv
    fi
    
    echo "🔄 Activating virtual environment..."
    source venv/bin/activate
    
    echo "⬆️  Upgrading pip..."
    pip install --upgrade pip
    
    echo "📚 Installing Python dependencies..."
    pip install -r requirements.txt
    
    echo "🎭 Installing Playwright browsers..."
    venv/bin/playwright install chromium
    
    echo "🔧 Installing Playwright system dependencies..."
    sudo venv/bin/playwright install-deps
    
    echo "📁 Creating output directory..."
    mkdir -p output
    
    echo "✅ VM setup complete!"
    echo ""
    echo "Python version: $(python --version)"
    echo "Pip packages installed: $(pip list | wc -l)"
    echo "Playwright: $(playwright --version)"
  '

echo ""
echo "✅ VM environment ready!"
echo ""
echo "Next steps:"
echo "1. Test scraper: ./test_vm.sh"
echo "2. Deploy dashboard: ./deploy_dashboard.sh"
