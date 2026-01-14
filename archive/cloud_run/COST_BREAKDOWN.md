# Gujarat AnyROR Global Search - Cost Breakdown

## 💰 CHEAPEST POSSIBLE SETUP

### Option 1: Cloud Run Jobs (Recommended - Pay Per Use)

**Cost: ~$0.50 - $2.00 per full Gujarat search**

| Component | Free Tier | Cost After Free |
|-----------|-----------|-----------------|
| Cloud Run Jobs | 2M vCPU-seconds/month | $0.00002400/vCPU-second |
| Cloud Run Jobs | 1M GiB-seconds/month | $0.00000250/GiB-second |
| Firestore | 1GB storage, 50K reads/day | $0.18/GB, $0.06/100K reads |
| Gemini API | 15 RPM free | $0.00025/1K chars after |

**Example: Full Gujarat Search (34 districts, 308 talukas, 18,511 villages)**

```
Assuming 30 seconds per village average:
- Total time: 18,511 × 30s = 555,330 seconds = ~154 hours
- With 34 parallel jobs: ~4.5 hours wall time

Cost breakdown:
- vCPU: 555,330 × $0.000024 = $13.33
- Memory (1GB): 555,330 × $0.0000025 = $1.39
- Gemini (1 captcha per village): 18,511 × $0.00025 = $4.63
- Firestore: Free tier covers it

Total: ~$19.35 for FULL Gujarat search
Per district: ~$0.57
```

### Option 2: Cloud Run Service (Always Available API)

**Cost: $0 when idle (scales to 0)**

| Usage | Monthly Cost |
|-------|--------------|
| Idle (0 requests) | $0 |
| 100 searches/month | ~$2-5 |
| 1000 searches/month | ~$15-30 |

### Option 3: Hybrid (Recommended for Production)

```
Cloud Run Service (API) → Triggers → Cloud Run Jobs (Workers)
         ↓                                    ↓
    Firestore ←─────────────────────────────────
```

- API handles requests, scales to 0 when idle
- Jobs do heavy lifting, pay only when running
- Firestore stores results (free tier: 1GB)

## 🎯 Cost Optimization Tips

1. **Use Cloud Run Jobs, not Services** for batch work
2. **Set min-instances=0** to scale to zero
3. **Use asia-south1** region (closest to Gujarat, cheaper)
4. **Batch requests** - search multiple surveys in one job
5. **Cache results** in Firestore to avoid re-scraping
6. **Use Gemini Flash** (cheapest model) for captcha

## 📊 Comparison with Alternatives

| Option | Monthly Cost (1000 searches) | Pros | Cons |
|--------|------------------------------|------|------|
| Cloud Run Jobs | ~$15-20 | Cheapest, scales to 0 | Cold start delay |
| Cloud Run Service | ~$20-30 | Always ready | Costs when idle |
| Cloud Functions | ~$25-35 | Simple | 9 min timeout limit |
| Compute Engine | ~$50-100 | Full control | Always running |
| AWS Lambda | ~$30-40 | Good scaling | Complex setup |

## 🚀 Quick Start (Cheapest)

```bash
# 1. Set up project
export GCP_PROJECT=anyror-scraper
export GEMINI_API_KEY=your-key

# 2. Deploy (one-time)
cd cloud_run
chmod +x deploy.sh
./deploy.sh

# 3. Run a district search (~$0.57)
gcloud run jobs execute anyror-district-search \
  --region asia-south1 \
  --args="--district,01,--search-value,123"

# 4. Check results
curl https://anyror-api-xxxxx.asia-south1.run.app/jobs/latest
```

## 💡 Even Cheaper: Local + Cloud Hybrid

Run scraper locally, use Cloud only for:
- Firestore (free tier for storage)
- Gemini API (free tier for captcha)

```python
# Local scraping with cloud captcha
from google import genai
client = genai.Client(api_key="...")
# Solve captcha via API, scrape locally
```

**Cost: ~$0.05 per 100 captchas** (Gemini free tier: 15 RPM)
