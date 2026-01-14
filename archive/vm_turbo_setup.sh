#!/bin/bash
# ============================================
# TURBO VM SETUP - 500-999 Villages in 10 Minutes
# ============================================
# Strategy: High-CPU VM + 50 Parallel Browser Tabs
# Target: ~1 village/second = 600 villages in 10 min
# ============================================

set -e

PROJECT_ID="${PROJECT_ID:-anyror-scraper-2026}"
ZONE="asia-south1-a"
VM_NAME="anyror-turbo"
MACHINE_TYPE="n2-standard-16"  # 16 vCPU, 64GB RAM - handles 50 parallel tabs easily

echo "============================================"
echo "🚀 TURBO VM SETUP"
echo "   Target: 500-999 villages in 10 minutes"
echo "   Machine: $MACHINE_TYPE (16 vCPU, 64GB)"
echo "============================================"

# Create VM if not exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    echo "📦 Creating VM..."
    gcloud compute instances create $VM_NAME \
        --project=$PROJECT_ID \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=50GB \
        --boot-disk-type=pd-ssd \
        --scopes=cloud-platform \
        --tags=http-server,https-server
    
    echo "⏳ Waiting for VM to be ready..."
    sleep 30
fi

# Start VM if stopped
gcloud compute instances start $VM_NAME --zone=$ZONE --project=$PROJECT_ID 2>/dev/null || true
sleep 10

echo "🔧 Installing dependencies..."
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="
set -e

# Install Python and dependencies
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv chromium-browser

# Create workspace
sudo mkdir -p /opt/scraper
sudo chown \$(whoami) /opt/scraper
cd /opt/scraper

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -q playwright==1.41.0 google-genai==1.0.0 google-cloud-storage==2.14.0 aiohttp==3.9.1

# Install Playwright browsers
playwright install chromium
playwright install-deps chromium

echo '✅ Dependencies installed'
"

echo "📤 Uploading scraper files..."
gcloud compute scp --recurse \
    turbo_vm_worker.py \
    gujarat-anyror-complete.json \
    $VM_NAME:/opt/scraper/ \
    --zone=$ZONE --project=$PROJECT_ID

echo ""
echo "============================================"
echo "✅ VM READY!"
echo "============================================"
echo ""
echo "Run scraper:"
echo "  ./run_turbo_vm.sh --district 30 --survey 10"
echo ""
echo "Or SSH and run manually:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
echo "  cd /opt/scraper && source venv/bin/activate"
echo "  python turbo_vm_worker.py --district 30 --survey 10 --parallel 50"
echo ""
