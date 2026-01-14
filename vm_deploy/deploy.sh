#!/bin/bash
# Deploy scraper files to VM
# Usage: ./deploy.sh <vm-ip> [ssh-key]

VM_IP="${1:-}"
SSH_KEY="${2:-}"

if [ -z "$VM_IP" ]; then
    echo "Usage: ./deploy.sh <vm-ip> [ssh-key]"
    echo "Example: ./deploy.sh 35.200.100.50 ~/.ssh/gcp-key"
    exit 1
fi

SSH_OPTS=""
if [ -n "$SSH_KEY" ]; then
    SSH_OPTS="-i $SSH_KEY"
fi

echo "=========================================="
echo "Deploying to VM: $VM_IP"
echo "=========================================="

# Files to deploy
FILES=(
    "vm_api.py"
    "vm_bulk_scraper.py"
    "vm_bulk_scraper_api.py"
    "vf7_extractor.py"
    "vf7_report.py"
    "captcha_solver.py"
    "gujarat-anyror-complete.json"
    "vm_deploy/setup.sh"
    "vm_deploy/run.sh"
)

# Create remote directory
ssh $SSH_OPTS $VM_IP "mkdir -p ~/anyror-scraper"

# Copy files
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "📤 Copying $file..."
        scp $SSH_OPTS "$file" "$VM_IP:~/anyror-scraper/$(basename $file)"
    fi
done

# Make scripts executable
ssh $SSH_OPTS $VM_IP "chmod +x ~/anyror-scraper/*.sh 2>/dev/null || true"

echo ""
echo "=========================================="
echo "✅ Deployment complete!"
echo "=========================================="
echo ""
echo "SSH into VM and run:"
echo "  ssh $SSH_OPTS $VM_IP"
echo "  cd ~/anyror-scraper"
echo "  ./setup.sh              # First time only"
echo "  source venv/bin/activate"
echo "  python vm_api.py        # Start API server"
echo ""
echo "Then configure frontend with: http://$VM_IP:8000"
echo ""
