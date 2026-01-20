#!/bin/bash

VM_NAME="scraper-turbo"
ZONE="asia-south1-a"
REMOTE_DIR="~/anyror-scraper"

echo "⚡ Fast Syncing Python files to $VM_NAME..."

gcloud compute scp \
    swarm_scraper_experimental.py \
    db_manager.py \
    requirements.txt \
    $VM_NAME:$REMOTE_DIR \
    --zone=$ZONE

echo "✅ Sync Complete! Try running the script on the VM now."
