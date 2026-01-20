#!/bin/bash

# VM Test Script
# Runs test scraper on VM to validate setup

set -e

VM_NAME="scraper-turbo"
ZONE="asia-south1-a"
PROJECT="anyror-scraper-2026"

echo "🧪 Testing scraper on VM..."
echo "VM: $VM_NAME"
echo ""

gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command='
    cd ~/anyror-scraper
    source venv/bin/activate
    
    echo "🚀 Running test with 10 villages..."
    echo ""
    
    python3 test_local_performance.py
    
    echo ""
    echo "✅ Test complete!"
    echo ""
    echo "Results:"
    ls -lh output/
  '

echo ""
echo "✅ VM test successful!"
echo ""
echo "Download results:"
echo "gcloud compute scp --zone=$ZONE --project=$PROJECT --recurse $VM_NAME:~/anyror-scraper/output/ ./vm-results/"
