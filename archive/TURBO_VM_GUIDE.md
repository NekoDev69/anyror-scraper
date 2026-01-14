# 🚀 TURBO VM Guide - 500-999 Villages in 10 Minutes

## Quick Start

```bash
# 1. Setup VM (one-time)
chmod +x vm_turbo_setup.sh
./vm_turbo_setup.sh

# 2. Run scraper
chmod +x run_turbo_vm.sh
./run_turbo_vm.sh --district 30 --survey 10
```

## Performance Targets

| Villages | Parallel Tabs | Time | Machine |
|----------|---------------|------|---------|
| 500 | 50 | ~10 min | n2-standard-8 |
| 999 | 50 | ~17 min | n2-standard-16 |
| 999 | 100 | ~10 min | n2-standard-16 + Paid API |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GCE VM (n2-standard-16)              │
│                    16 vCPU, 64GB RAM                    │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐   │
│  │           Playwright Browser (Chromium)          │   │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ... ┌─────┐   │   │
│  │  │Tab 1│ │Tab 2│ │Tab 3│ │Tab 4│     │Tab50│   │   │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘     └──┬──┘   │   │
│  └─────┼───────┼───────┼───────┼───────────┼──────┘   │
│        │       │       │       │           │          │
│        ▼       ▼       ▼       ▼           ▼          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              AnyROR Portal (parallel)            │   │
│  └─────────────────────────────────────────────────┘   │
│        │                                              │
│        ▼                                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Gemini API (rate-limited 15 RPM)         │   │
│  └─────────────────────────────────────────────────┘   │
│        │                                              │
│        ▼                                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │              GCS Bucket (results)                │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Bottleneck: Gemini API Rate Limit

The **main bottleneck** is Gemini's free tier: **15 requests/minute**.

### Option 1: Free Tier (15 RPM)
- ~15 captcha solves per minute
- With 50 parallel tabs, most wait for captcha
- **Effective rate: ~15 villages/min with survey filter**
- 500 villages = ~33 minutes

### Option 2: Paid Gemini API (1500 RPM)
- Upgrade to paid tier: ~$0.001 per captcha
- **Effective rate: ~60 villages/min**
- 500 villages = ~8 minutes
- 999 villages = ~17 minutes

### Option 3: Multiple API Keys (Hack)
```bash
# Use multiple free API keys (rotate)
export GEMINI_API_KEYS="key1,key2,key3,key4"
```

## Machine Sizing

| Machine Type | vCPU | RAM | Max Tabs | Cost/hr |
|--------------|------|-----|----------|---------|
| n2-standard-4 | 4 | 16GB | 20 | $0.19 |
| n2-standard-8 | 8 | 32GB | 40 | $0.39 |
| n2-standard-16 | 16 | 64GB | 80 | $0.78 |
| n2-standard-32 | 32 | 128GB | 150 | $1.55 |

**Recommended: n2-standard-16** - Best balance of cost and performance.

## Commands

### Setup VM
```bash
./vm_turbo_setup.sh
```

### Run Scraper
```bash
# Single district, specific survey
./run_turbo_vm.sh --district 30 --survey 10

# Single district, all surveys (needs paid API)
./run_turbo_vm.sh --district 30 --parallel 100

# With more parallel tabs
./run_turbo_vm.sh --district 30 --survey 10 --parallel 80
```

### SSH to VM
```bash
gcloud compute ssh anyror-turbo --zone=asia-south1-a --project=anyror-scraper-2026
cd /opt/scraper && source venv/bin/activate
python turbo_vm_worker.py --district 30 --survey 10 --parallel 50
```

### Download Results
```bash
# From GCS
gsutil -m cp -r gs://anyror-results/30/* ./output/

# From VM
gcloud compute scp --recurse anyror-turbo:/opt/scraper/output/* ./output/
```

### Stop VM (save costs)
```bash
gcloud compute instances stop anyror-turbo --zone=asia-south1-a
```

## Cost Estimate

| Component | Cost |
|-----------|------|
| VM (n2-standard-16, 1 hour) | $0.78 |
| Gemini API (free tier) | $0 |
| GCS Storage (1GB) | $0.02 |
| **Total for 999 villages** | **~$1** |

## For Maximum Speed (999 villages in 10 min)

You need to bypass the Gemini rate limit:

### Option A: Paid Gemini API
```bash
# Get paid API key from Google AI Studio
export GEMINI_API_KEY="your-paid-key"
# Modify turbo_vm_worker.py: rpm=1500
```

### Option B: Multiple VMs (Parallel Districts)
```bash
# Run 3 VMs, each handling 333 villages
./run_multi_vm.sh --district 30 --instances 3
```

### Option C: Pre-solve Captchas
- Cache common captcha patterns
- Use local ML model for simple captchas
- Only use Gemini for hard ones

## Troubleshooting

### VM won't start
```bash
gcloud compute instances start anyror-turbo --zone=asia-south1-a
```

### Browser crashes
- Reduce parallel tabs: `--parallel 30`
- Use larger VM: `n2-standard-32`

### Rate limited
- Wait 1 minute and retry
- Use paid API key
- Reduce parallel tabs

### No results
- Check GCS: `gsutil ls gs://anyror-results/`
- Check VM logs: `gcloud compute ssh anyror-turbo --command="tail -100 /opt/scraper/output/*.log"`
