#!/bin/bash

VM_NAME="scraper-turbo"
ZONE="asia-south1-a"
REMOTE_DIR="~/anyror-scraper"

echo "🚀 Deploying to $VM_NAME in $ZONE..."

# 1. Create directory on VM
gcloud compute ssh $VM_NAME --zone=$ZONE --command "mkdir -p $REMOTE_DIR"

# 2. Upload Files
echo "📦 Uploading files..."
gcloud compute scp \
    swarm_scraper_experimental.py \
    captcha_solver.py \
    vf7_extractor.py \
    excel_exporter.py \
    db_manager.py \
    db_schema.sql \
    requirements.txt \
    .env \
    vm_api.py \
    vertex-credentials.json \
    gujarat-anyror-complete.json \
    $VM_NAME:$REMOTE_DIR \
    --zone=$ZONE

# 3. Setup Environment (Remote Execution)
echo "🔧 Setting up environment on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command "
    cd $REMOTE_DIR
    
    # Install System Deps
    sudo apt update
    sudo apt install -y python3-pip python3-venv unzip

    # Create Venv
    if [ ! -d 'venv' ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    
    # Install Python Libs
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Install Playwright Browsers
    playwright install chromium --with-deps
    
    echo '✅ Setup Complete!'
"

echo "🎉 Deployment Finished! You can now SSH into the VM:"
echo "gcloud compute ssh $VM_NAME --zone=$ZONE"
