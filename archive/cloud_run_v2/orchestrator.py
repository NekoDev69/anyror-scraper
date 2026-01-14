"""
Orchestrator VM - Manages Cloud Run Jobs
Runs on e2-micro VM (~$6/mo)

Features:
- Web UI to select districts and trigger searches
- REST API to trigger searches
- Tracks job progress
- Stores results in SQLite (free)
- Triggers Cloud Run Jobs for each district
"""

import os
import json
import sqlite3
import subprocess
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Config
PROJECT_ID = os.environ.get("GCP_PROJECT", "anyror-scraper-2026")
REGION = os.environ.get("GCP_REGION", "asia-south1")
JOB_NAME = os.environ.get("JOB_NAME", "anyror-district-scraper-opt")  # Optimized job
DB_PATH = os.environ.get("DB_PATH", "jobs.db")
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Load Gujarat data
GUJARAT_DATA_PATH = os.environ.get("GUJARAT_DATA", "gujarat-anyror-complete.json")
with open(GUJARAT_DATA_PATH, "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)

DISTRICTS = {d["value"]: d for d in GUJARAT_DATA["districts"]}

app = FastAPI(title="AnyROR Global Search Orchestrator")


# Database setup
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            district_code TEXT,
            district_name TEXT,
            survey_number TEXT,
            status TEXT DEFAULT 'pending',
            talukas_total INTEGER DEFAULT 0,
            talukas_scraped INTEGER DEFAULT 0,
            villages_total INTEGER DEFAULT 0,
            villages_scraped INTEGER DEFAULT 0,
            total_surveys INTEGER DEFAULT 0,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            result_json TEXT,
            error TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# Models
class SearchRequest(BaseModel):
    district_code: str
    survey_number: str = ""
    parallel_contexts: int = 5


class MultiDistrictRequest(BaseModel):
    district_codes: List[str]  # List of district codes to search
    survey_number: str = ""
    parallel_contexts: int = 5


class AllDistrictsRequest(BaseModel):
    survey_number: str = ""
    parallel_contexts: int = 5


# ============================================
# Frontend Routes
# ============================================

@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the frontend"""
    html_path = TEMPLATES_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


# ============================================
# API Routes (prefixed with /api)
# ============================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "project": PROJECT_ID,
        "region": REGION,
        "districts_available": len(DISTRICTS)
    }


@app.get("/api/districts")
def list_districts():
    """List all 34 districts with stats"""
    return [
        {
            "code": d["value"],
            "name": d["label"],
            "talukas": len(d["talukas"]),
            "villages": sum(len(t["villages"]) for t in d["talukas"])
        }
        for d in GUJARAT_DATA["districts"]
    ]


@app.get("/api/districts/{code}")
def get_district(code: str):
    """Get district details"""
    district = DISTRICTS.get(code)
    if not district:
        raise HTTPException(404, "District not found")
    
    return {
        "code": district["value"],
        "name": district["label"],
        "talukas": [
            {
                "code": t["value"],
                "name": t["label"],
                "villages": len(t["villages"])
            }
            for t in district["talukas"]
        ]
    }


@app.post("/api/search/district")
async def search_district(req: SearchRequest, background_tasks: BackgroundTasks):
    """Trigger Cloud Run Job for a single district"""
    
    district = DISTRICTS.get(req.district_code)
    if not district:
        raise HTTPException(404, f"District {req.district_code} not found")
    
    job_id = f"search_{req.district_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create job record
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO jobs (job_id, district_code, district_name, status, 
                         talukas_total, villages_total, created_at, survey_number)
        VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
    """, (
        job_id,
        req.district_code,
        district["label"],
        len(district["talukas"]),
        sum(len(t["villages"]) for t in district["talukas"]),
        datetime.utcnow().isoformat(),
        req.survey_number
    ))
    conn.commit()
    conn.close()
    
    # Trigger Cloud Run Job in background
    background_tasks.add_task(
        trigger_cloud_run_job,
        job_id,
        district,
        req.parallel_contexts,
        req.survey_number
    )
    
    return {
        "job_id": job_id,
        "jobs_created": 1,
        "status": "pending",
        "district": district["label"],
        "talukas": len(district["talukas"]),
        "villages": sum(len(t["villages"]) for t in district["talukas"]),
        "message": "Job queued, Cloud Run Job will be triggered"
    }


@app.post("/api/search/multi")
async def search_multiple_districts(req: MultiDistrictRequest, background_tasks: BackgroundTasks):
    """Trigger Cloud Run Jobs for multiple districts in parallel"""
    
    jobs = []
    
    for code in req.district_codes:
        district = DISTRICTS.get(code)
        if not district:
            continue
        
        job_id = f"search_{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create job record
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO jobs (job_id, district_code, district_name, status,
                             talukas_total, villages_total, created_at, survey_number)
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
        """, (
            job_id,
            code,
            district["label"],
            len(district["talukas"]),
            sum(len(t["villages"]) for t in district["talukas"]),
            datetime.utcnow().isoformat(),
            req.survey_number
        ))
        conn.commit()
        conn.close()
        
        # Trigger job
        background_tasks.add_task(
            trigger_cloud_run_job,
            job_id,
            district,
            req.parallel_contexts,
            req.survey_number
        )
        
        jobs.append({
            "job_id": job_id,
            "district": district["label"]
        })
    
    return {
        "jobs_created": len(jobs),
        "jobs": jobs
    }


@app.post("/api/search/all")
async def search_all_districts(req: AllDistrictsRequest, background_tasks: BackgroundTasks):
    """Trigger Cloud Run Jobs for ALL 34 districts"""
    
    jobs = []
    
    for district in GUJARAT_DATA["districts"]:
        job_id = f"search_{district['value']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO jobs (job_id, district_code, district_name, status,
                             talukas_total, villages_total, created_at, survey_number)
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
        """, (
            job_id,
            district["value"],
            district["label"],
            len(district["talukas"]),
            sum(len(t["villages"]) for t in district["talukas"]),
            datetime.utcnow().isoformat(),
            req.survey_number
        ))
        conn.commit()
        conn.close()
        
        background_tasks.add_task(
            trigger_cloud_run_job,
            job_id,
            district,
            req.parallel_contexts,
            req.survey_number
        )
        
        jobs.append({"job_id": job_id, "district": district["label"]})
    
    return {
        "message": "Triggered search for ALL 34 districts",
        "jobs_created": len(jobs),
        "estimated_time": "~30-60 minutes with parallel execution"
    }


@app.get("/api/jobs")
def list_jobs(status: Optional[str] = None, limit: int = 50):
    """List all jobs"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    if status:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Get job details"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(404, "Job not found")
    
    result = dict(row)
    if result.get("result_json"):
        result["result"] = json.loads(result["result_json"])
        del result["result_json"]
    
    return result


@app.post("/api/progress")
async def update_progress(data: dict):
    """Webhook endpoint for Cloud Run Jobs to report progress"""
    
    job_id = data.get("job_id")
    if not job_id:
        return {"error": "job_id required"}
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs SET
            status = 'running',
            talukas_scraped = ?,
            villages_scraped = ?,
            total_surveys = ?,
            started_at = COALESCE(started_at, ?)
        WHERE job_id = ?
    """, (
        data.get("talukas_scraped", 0),
        data.get("villages_scraped", 0),
        data.get("total_surveys", 0),
        datetime.utcnow().isoformat(),
        job_id
    ))
    conn.commit()
    conn.close()
    
    return {"status": "updated"}


@app.post("/api/complete")
async def job_complete(data: dict):
    """Webhook endpoint for Cloud Run Jobs to report completion"""
    
    job_id = data.get("job_id")
    if not job_id:
        return {"error": "job_id required"}
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs SET
            status = 'completed',
            talukas_scraped = ?,
            villages_scraped = ?,
            total_surveys = ?,
            completed_at = ?,
            result_json = ?
        WHERE job_id = ?
    """, (
        data.get("talukas_scraped", 0),
        data.get("villages_scraped", 0),
        data.get("total_surveys", 0),
        datetime.utcnow().isoformat(),
        json.dumps(data, ensure_ascii=False),
        job_id
    ))
    conn.commit()
    conn.close()
    
    print(f"[COMPLETE] Job {job_id}: {data.get('total_surveys', 0)} surveys found")
    
    return {"status": "completed"}


# Cloud Run Job trigger
def trigger_cloud_run_job(job_id: str, district: dict, parallel_contexts: int, survey_number: str = ""):
    """Trigger Cloud Run Job via gcloud CLI"""
    
    try:
        # Update status
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE jobs SET status = 'starting' WHERE job_id = ?", (job_id,))
        conn.commit()
        conn.close()
        
        # Get orchestrator URL for webhook
        orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8080")
        
        # Prepare district data as JSON (escape for shell)
        district_json = json.dumps(district, ensure_ascii=False)
        
        # Execute Cloud Run Job
        cmd = [
            "gcloud", "run", "jobs", "execute", JOB_NAME,
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
            "--async",  # Don't wait for completion
            f"--update-env-vars=JOB_ID={job_id},PARALLEL_CONTEXTS={parallel_contexts},RESULTS_WEBHOOK={orchestrator_url}/api,SURVEY_NUMBER={survey_number}"
        ]
        
        # Pass district data via a different method (file or base64) for large data
        # For now, we'll use environment variable with base64 encoding
        import base64
        district_b64 = base64.b64encode(district_json.encode()).decode()
        cmd[-1] += f",DISTRICT_DATA_B64={district_b64}"
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"[TRIGGERED] Job {job_id} for district {district['label']}")
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE jobs SET status = 'running', started_at = ? WHERE job_id = ?",
                        (datetime.utcnow().isoformat(), job_id))
            conn.commit()
            conn.close()
        else:
            print(f"[ERROR] Failed to trigger job: {result.stderr}")
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE jobs SET status = 'error', error = ? WHERE job_id = ?",
                        (result.stderr, job_id))
            conn.commit()
            conn.close()
            
    except Exception as e:
        print(f"[ERROR] {e}")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE jobs SET status = 'error', error = ? WHERE job_id = ?",
                    (str(e), job_id))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
