#!/bin/bash

# VM Manager - Master script for all VM operations
# Usage: ./vm_manager.sh [command]

set -e

VM_NAME="scraper-turbo"
ZONE="asia-south1-a"
PROJECT="anyror-scraper-2026"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

show_help() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 VM Manager - AnyROR Scraper"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Usage: ./vm_manager.sh [command]"
    echo ""
    echo "Commands:"
    echo "  check       - Check VM status and resources"
    echo "  sync        - Sync local code to VM"
    echo "  setup       - Setup VM environment (install dependencies)"
    echo "  test        - Run test scraper on VM"
    echo "  deploy      - Deploy dashboard service"
    echo "  download    - Download results from VM"
    echo "  ssh         - SSH into VM"
    echo "  logs        - View dashboard logs"
    echo "  restart     - Restart dashboard service"
    echo "  stop        - Stop dashboard service"
    echo "  start       - Start dashboard service"
    echo "  full-setup  - Complete setup (sync + setup + deploy)"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./vm_manager.sh check"
    echo "  ./vm_manager.sh full-setup"
    echo "  ./vm_manager.sh logs"
    echo ""
}

case "$1" in
    check)
        echo -e "${BLUE}🔍 Checking VM status...${NC}"
        ./check_vm.sh
        ;;
    
    sync)
        echo -e "${BLUE}🔄 Syncing code to VM...${NC}"
        ./sync_to_vm.sh
        ;;
    
    setup)
        echo -e "${BLUE}🔧 Setting up VM environment...${NC}"
        ./setup_vm.sh
        ;;
    
    test)
        echo -e "${BLUE}🧪 Testing scraper on VM...${NC}"
        ./test_vm.sh
        ;;
    
    deploy)
        echo -e "${BLUE}🎨 Deploying dashboard...${NC}"
        ./deploy_dashboard.sh
        ;;
    
    download)
        echo -e "${BLUE}⬇️  Downloading results...${NC}"
        ./download_results.sh
        ;;
    
    ssh)
        echo -e "${BLUE}🔐 Connecting to VM...${NC}"
        gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT
        ;;
    
    logs)
        echo -e "${BLUE}📋 Viewing dashboard logs...${NC}"
        gcloud compute ssh $VM_NAME \
          --zone=$ZONE \
          --project=$PROJECT \
          --command="sudo journalctl -u anyror-dashboard -f"
        ;;
    
    restart)
        echo -e "${YELLOW}🔄 Restarting dashboard...${NC}"
        gcloud compute ssh $VM_NAME \
          --zone=$ZONE \
          --project=$PROJECT \
          --command="sudo systemctl restart anyror-dashboard"
        echo -e "${GREEN}✅ Dashboard restarted${NC}"
        ;;
    
    stop)
        echo -e "${YELLOW}⏸️  Stopping dashboard...${NC}"
        gcloud compute ssh $VM_NAME \
          --zone=$ZONE \
          --project=$PROJECT \
          --command="sudo systemctl stop anyror-dashboard"
        echo -e "${GREEN}✅ Dashboard stopped${NC}"
        ;;
    
    start)
        echo -e "${BLUE}▶️  Starting dashboard...${NC}"
        gcloud compute ssh $VM_NAME \
          --zone=$ZONE \
          --project=$PROJECT \
          --command="sudo systemctl start anyror-dashboard"
        echo -e "${GREEN}✅ Dashboard started${NC}"
        ;;
    
    full-setup)
        echo -e "${BLUE}🚀 Running full setup...${NC}"
        echo ""
        echo "This will:"
        echo "  1. Sync code to VM"
        echo "  2. Setup environment"
        echo "  3. Deploy dashboard"
        echo ""
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ./sync_to_vm.sh
            echo ""
            ./setup_vm.sh
            echo ""
            ./deploy_dashboard.sh
            echo ""
            echo -e "${GREEN}✅ Full setup complete!${NC}"
        else
            echo "Cancelled"
        fi
        ;;
    
    help|--help|-h|"")
        show_help
        ;;
    
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
