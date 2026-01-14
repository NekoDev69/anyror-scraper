# Gujarat AnyROR Global Search System

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   YOU                                                                    │
│    │                                                                     │
│    ▼                                                                     │
│   ┌──────────────────────────────────────┐                              │
│   │     Orchestrator VM (e2-micro)       │  ← Always on (~$6/mo)        │
│   │     http://VM_IP:8080                │                              │
│   │                                      │                              │
│   │  • REST API                          │                              │
│   │  • Job management                    │                              │
│   │  • SQLite results DB                 │                              │
│   │  • Triggers Cloud Run Jobs           │                              │
│   └──────────────────┬───────────────────┘                              │
│                      │                                                   │
│                      │ triggers (up to 34 parallel)                     │
│                      ▼                                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                  Cloud Run Jobs (pay per use)                    │   │
│   │                                                                  │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │   │
│   │  │ District 01 │  │ District 02 │  │ District 34 │   ...        │   │
│   │  │   (કચ્છ)    │  │  (બનાસકાંઠા) │  │   (તાપી)    │              │   │
│   │  │             │  │             │  │             │              │   │
│   │  │ 5 parallel  │  │ 5 parallel  │  │ 5 parallel  │              │   │
│   │  │ browsers    │  │ browsers    │  │ browsers    │              │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘              │   │
│   │                                                                  │   │
│   │  Each job: 2 vCPU, 2GB RAM, ~$0.50-1.00 per district            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                      │                                                   │
│                      │ results webhook                                  │
│                      ▼                                                   │
│   ┌──────────────────────────────────────┐                              │
│   │         SQLite on VM                 │  ← Free                      │
│   │     (jobs.db - results storage)      │                              │
│   └──────────────────────────────────────┘                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Speed Comparison

| Approach | 500 Villages | Full Gujarat (18,511) |
|----------|--------------|----------------------|
| Single browser | 4+ hours | 154 hours |
| 5 parallel (1 job) | 50 min | 31 hours |
| 34 parallel jobs × 5 browsers | 10 min | **~1 hour** |

## Cost Breakdown

### Fixed Costs (Monthly)
| Resource | Cost |
|----------|------|
| e2-micro VM (orchestrator) | ~$6/mo |
| **Total Fixed** | **~$6/mo** |

### Variable Costs (Per Search)
| Resource | Per District | Full Gujarat |
|----------|--------------|--------------|
| Cloud Run Job (2 vCPU, 2GB, ~30min) | ~$0.50 | ~$17 |
| Gemini API (captcha) | ~$0.15 | ~$5 |
| **Total Per Search** | **~$0.65** | **~$22** |

### Monthly Estimates
| Usage | Cost |
|-------|------|
| Idle (VM only) | $6 |
| 10 district searches | $6 + $6.50 = $12.50 |
| 1 full Gujarat search | $6 + $22 = $28 |
| 10 full Gujarat searches | $6 + $220 = $226 |

## API Endpoints

### List Districts
```bash
curl http://VM_IP:8080/districts
```

### Search Single District
```bash
curl -X POST http://VM_IP:8080/search/district \
  -H "Content-Type: application/json" \
  -d '{"district_code": "01", "parallel_contexts": 5}'
```

### Search Multiple Districts
```bash
curl -X POST http://VM_IP:8080/search/multi \
  -H "Content-Type: application/json" \
  -d '{"district_codes": ["01", "02", "03"]}'
```

### Search ALL Gujarat (34 parallel jobs)
```bash
curl -X POST http://VM_IP:8080/search/all
```

### Check Job Status
```bash
curl http://VM_IP:8080/jobs
curl http://VM_IP:8080/jobs/{job_id}
```

## Deployment

```bash
# Set environment
export GCP_PROJECT=anyror-scraper-2026
export GEMINI_API_KEY=your-key

# Deploy everything
chmod +x deploy.sh
./deploy.sh
```

## Files

```
cloud_run_v2/
├── parallel_worker.py      # Cloud Run Job - parallel browser scraping
├── orchestrator.py         # VM API - job management
├── Dockerfile.worker       # Worker container
├── Dockerfile.orchestrator # Orchestrator container (optional)
├── requirements-*.txt      # Dependencies
├── deploy.sh              # One-click deployment
└── README.md              # This file
```

## Real-time Editing

Since orchestrator runs on a VM, you can:
```bash
# SSH into VM
gcloud compute ssh anyror-orchestrator --zone=asia-south1-a

# Edit files directly
nano orchestrator.py

# Restart
pkill python3
nohup python3 orchestrator.py > orchestrator.log 2>&1 &
```

For worker changes, rebuild and update the Cloud Run Job:
```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/anyror-worker --dockerfile Dockerfile.worker .
gcloud run jobs update anyror-district-scraper --image=gcr.io/$PROJECT_ID/anyror-worker
```
