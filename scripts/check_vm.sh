#!/bin/bash

# VM Status Check Script
# Checks VM status, services, and resources

set -e

VM_NAME="scraper-turbo"
ZONE="asia-south1-a"
PROJECT="anyror-scraper-2026"

echo "🔍 Checking VM status..."
echo ""

# Get VM info
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 VM Information"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
gcloud compute instances describe $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --format="table(
    name,
    status,
    machineType.basename(),
    networkInterfaces[0].accessConfigs[0].natIP:label=EXTERNAL_IP
  )"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 System Resources"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command='
    echo "CPU Cores: $(nproc)"
    echo "Memory: $(free -h | grep Mem | awk "{print \$2}")"
    echo "Disk Usage: $(df -h / | tail -1 | awk "{print \$3 \" / \" \$2 \" (\" \$5 \" used)\"}")"
    echo "Load Average: $(uptime | awk -F"load average:" "{print \$2}")"
  '

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installed Software"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command='
    echo "Python: $(python3 --version 2>&1)"
    if [ -d ~/anyror-scraper/venv ]; then
      source ~/anyror-scraper/venv/bin/activate
      echo "Playwright: $(playwright --version 2>&1 || echo "Not installed")"
      echo "Pip packages: $(pip list | wc -l) installed"
    else
      echo "Virtual environment: Not created"
    fi
  '

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 Dashboard Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command='
    if systemctl is-active --quiet anyror-dashboard; then
      echo "Status: ✅ RUNNING"
      echo "Uptime: $(systemctl show anyror-dashboard -p ActiveEnterTimestamp --value | xargs -I {} date -d {} +"%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "Unknown")"
    else
      echo "Status: ❌ NOT RUNNING"
    fi
  '

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 Project Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command='
    if [ -d ~/anyror-scraper ]; then
      echo "Project directory: ✅ EXISTS"
      echo "Files: $(find ~/anyror-scraper -type f | wc -l)"
      echo "Size: $(du -sh ~/anyror-scraper | cut -f1)"
      if [ -d ~/anyror-scraper/output ]; then
        echo "Output files: $(find ~/anyror-scraper/output -type f | wc -l)"
      fi
    else
      echo "Project directory: ❌ NOT FOUND"
    fi
  '

# Get VM external IP
VM_IP=$(gcloud compute instances describe $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔗 Quick Links"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Dashboard: http://$VM_IP:5001"
echo "SSH: gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT"
echo ""
