#!/bin/bash

# Dashboard Deployment Script
# Deploys Flask dashboard as systemd service on VM

set -e

VM_NAME="scraper-turbo"
ZONE="asia-south1-a"
PROJECT="anyror-scraper-2026"

echo "🎨 Deploying dashboard to VM..."
echo "VM: $VM_NAME"
echo ""

# Create and start systemd service
echo "📝 Creating systemd service..."
gcloud compute ssh $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --command='
    # Create service file
    sudo tee /etc/systemd/system/anyror-dashboard.service > /dev/null << SERVICE
[Unit]
Description=AnyROR Scraper Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/anyror-scraper
Environment="PATH=/home/$USER/anyror-scraper/venv/bin"
ExecStart=/home/$USER/anyror-scraper/venv/bin/python dashboard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable service to start on boot
    sudo systemctl enable anyror-dashboard
    
    # Start service
    sudo systemctl start anyror-dashboard
    
    # Wait a moment for service to start
    sleep 2
    
    # Check status
    sudo systemctl status anyror-dashboard --no-pager
    
    echo ""
    echo "✅ Dashboard service started!"
  '

# Open firewall port
echo ""
echo "🔥 Configuring firewall..."
gcloud compute firewall-rules create allow-dashboard \
  --project=$PROJECT \
  --allow=tcp:5001 \
  --source-ranges=0.0.0.0/0 \
  --description="Allow AnyROR dashboard access" \
  2>/dev/null && echo "✅ Firewall rule created" || echo "ℹ️  Firewall rule already exists"

# Get VM external IP
VM_IP=$(gcloud compute instances describe $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "✅ Dashboard deployed successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Access Dashboard:"
echo "   http://$VM_IP:5001"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Useful commands:"
echo "  Check status:  gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT --command='sudo systemctl status anyror-dashboard'"
echo "  View logs:     gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT --command='sudo journalctl -u anyror-dashboard -f'"
echo "  Restart:       gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT --command='sudo systemctl restart anyror-dashboard'"
echo "  Stop:          gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT --command='sudo systemctl stop anyror-dashboard'"
