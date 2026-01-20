#!/bin/bash

# Download Results Script
# Downloads scraper results from VM to local machine

set -e

VM_NAME="scraper-turbo"
ZONE="asia-south1-a"
PROJECT="anyror-scraper-2026"
LOCAL_DIR="./vm-results"

echo "⬇️  Downloading results from VM..."
echo "VM: $VM_NAME"
echo "Local directory: $LOCAL_DIR"
echo ""

# Create local directory
mkdir -p $LOCAL_DIR

# Download output directory
echo "📦 Downloading output files..."
gcloud compute scp \
  --zone=$ZONE \
  --project=$PROJECT \
  --recurse \
  $VM_NAME:~/anyror-scraper/output/ \
  $LOCAL_DIR/

echo ""
echo "✅ Download complete!"
echo ""
echo "Results saved to: $LOCAL_DIR"
echo ""
echo "Files:"
ls -lh $LOCAL_DIR/output/
