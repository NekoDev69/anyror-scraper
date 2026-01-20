#!/bin/bash

# GCP VM Sync Script
# Syncs local codebase to GCP VM

# Usage: ./sync_to_vm.sh [VM_NAME]

set -e

VM_NAME=${1:-"scraper-turbo"}
ZONE="asia-south1-a"
PROJECT="anyror-scraper-2026"
REMOTE_DIR="~/anyror-scraper"

echo "🔄 Syncing code to GCP VM..."
echo "VM: $VM_NAME"
echo "Zone: $ZONE"
echo ""

# Create remote directory
echo "📁 Creating remote directory..."
gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command="mkdir -p $REMOTE_DIR"

# Sync Python files
echo "📦 Syncing Python files..."
gcloud compute scp \
  --zone=$ZONE \
  --project=$PROJECT \
  anyror_scraper.py \
  anyror_scraper_async.py \
  anyror_scraper_easyocr.py \
  captcha_solver.py \
  district_scraper.py \
  global_owner_scraper.py \
  db_manager.py \
  db_schema.sql \
  parallel_scraper.py \
  fixed_parallel_scraper.py \
  dashboard.py \
  vf7_extractor.py \
  swarm_scraper.py \
  swarm_scraper_experimental.py \
  vm_api.py \
  vm_manager.sh \
  test_local_performance.py \
  $VM_NAME:$REMOTE_DIR/

# Sync configuration files
echo "⚙️  Syncing configuration..."
gcloud compute scp \
  --zone=$ZONE \
  --project=$PROJECT \
  requirements.txt \
  .env \
  .gitignore \
  gujarat-anyror-complete.json \
  $VM_NAME:$REMOTE_DIR/

# Sync directories
echo "📂 Syncing directories..."
gcloud compute scp \
  --zone=$ZONE \
  --project=$PROJECT \
  --recurse \
  high_performance_scraper/ \
  templates/ \
  frontend/ \
  tests/ \
  $VM_NAME:$REMOTE_DIR/

# Sync documentation
echo "📄 Syncing documentation..."
gcloud compute scp \
  --zone=$ZONE \
  --project=$PROJECT \
  ARCHITECTURE.md \
  DASHBOARD_README.md \
  DASHBOARD_QUICKSTART.md \
  DISTRICT_SCRAPER_README.md \
  DISTRICT_SCRAPER_GUIDE.md \
  IMPROVEMENTS_SUMMARY.md \
  $VM_NAME:$REMOTE_DIR/ 2>/dev/null || echo "Some docs skipped"

echo ""
echo "✅ Sync complete!"
echo ""
echo "Next steps:"
echo "1. Setup VM: ./setup_vm.sh"
echo "2. Test scraper: ./test_vm.sh"
echo "3. Deploy dashboard: ./deploy_dashboard.sh"
