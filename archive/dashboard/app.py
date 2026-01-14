"""
AnyROR Dashboard - Local/Cloud deployable
Trigger district searches, track jobs, view results
"""

import os
import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Config
PROJECT_ID = os.environ.get("GCP_PROJECT", "anyror-scraper-2026")
REGION = os.environ.get("GCP_REGION", "asia-south1")
JOB_NAME = os.environ.get("JOB_NAME", "anyror-worker")
DB_PATH = os.environ.get("DB_PATH", "dashboard/jobs.db")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "output")

# Load Gujarat data
GUJARAT_PATH = Path(__file__).parent.parent / "gujarat-anyror-complete.json"
with open(GUJARAT_PATH, "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)

DISTRICTS = {d["value"]: d for d in GUJARAT_DATA["districts"]}

app = FastAPI(title="AnyROR Dashboard", version="1.0")

# Ensure directories exist
Path(RESULTS_DIR).mkdir(exist_ok=True)
Path(DB_PATH).parent.mkdir(exist_ok=True)


# ============================================
# Database
# ============================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE,
            district_code TEXT,
            district_name TEXT,
            survey_number TEXT,
            status TEXT DEFAULT 'pending',
            villages_total INTEGER DEFAULT 0,
            villages_done INTEGER DEFAULT 0,
            matches INTEGER DEFAULT 0,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            village TEXT,
            taluka TEXT,
            survey TEXT,
            file_path TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ============================================
# Models
# ============================================
class SearchRequest(BaseModel):
    district_code: str
    survey_number: str = ""


class MultiSearchRequest(BaseModel):
    district_codes: List[str]
    survey_number: str = ""


# ============================================
# API Routes
# ============================================
@app.get("/", response_class=HTMLResponse)
async def home():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/districts")
def get_districts():
    """List all 34 districts"""
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
    """Get district details with talukas"""
    district = DISTRICTS.get(code)
    if not district:
        raise HTTPException(404, "District not found")
    return {
        "code": district["value"],
        "name": district["label"],
        "talukas": [
            {"code": t["value"], "name": t["label"], "villages": len(t["villages"])}
            for t in district["talukas"]
        ]
    }


@app.post("/api/search")
async def trigger_search(req: SearchRequest, bg: BackgroundTasks):
    """Trigger Cloud Run job for a district"""
    district = DISTRICTS.get(req.district_code)
    if not district:
        raise HTTPException(404, f"District {req.district_code} not found")
    
    job_id = f"search_{req.district_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Save to DB
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO jobs (job_id, district_code, district_name, survey_number, status, 
                         villages_total, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?, ?)
    """, (
        job_id, req.district_code, district["label"], req.survey_number,
        sum(len(t["villages"]) for t in district["talukas"]),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()
    
    # Trigger in background
    bg.add_task(run_cloud_job, job_id, req.district_code, req.survey_number)
    
    return {
        "job_id": job_id,
        "district": district["label"],
        "survey": req.survey_number or "ALL",
        "status": "pending"
    }


@app.post("/api/search/multi")
async def trigger_multi_search(req: MultiSearchRequest, bg: BackgroundTasks):
    """Trigger searches for multiple districts"""
    jobs = []
    for code in req.district_codes:
        district = DISTRICTS.get(code)
        if not district:
            continue
        
        job_id = f"search_{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO jobs (job_id, district_code, district_name, survey_number, status,
                             villages_total, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (
            job_id, code, district["label"], req.survey_number,
            sum(len(t["villages"]) for t in district["talukas"]),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        conn.close()
        
        bg.add_task(run_cloud_job, job_id, code, req.survey_number)
        jobs.append({"job_id": job_id, "district": district["label"]})
    
    return {"jobs_created": len(jobs), "jobs": jobs}


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
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Get job details"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not job:
        raise HTTPException(404, "Job not found")
    
    results = conn.execute(
        "SELECT * FROM results WHERE job_id = ? ORDER BY created_at DESC", (job_id,)
    ).fetchall()
    
    conn.close()
    
    return {**dict(job), "results": [dict(r) for r in results]}


@app.get("/api/results")
def list_results(limit: int = 100):
    """List all results"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM results ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/results/{result_id}/html")
def get_result_html(result_id: int):
    """Get HTML report"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM results WHERE id = ?", (result_id,)).fetchone()
    conn.close()
    
    if not row or not row["file_path"]:
        raise HTTPException(404, "Result not found")
    
    html_path = row["file_path"].replace(".json", ".html")
    if Path(html_path).exists():
        return FileResponse(html_path, media_type="text/html")
    
    raise HTTPException(404, "HTML file not found")


@app.get("/api/stats")
def get_stats():
    """Dashboard stats"""
    conn = sqlite3.connect(DB_PATH)
    stats = {
        "total_jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "running_jobs": conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running'").fetchone()[0],
        "completed_jobs": conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'completed'").fetchone()[0],
        "total_results": conn.execute("SELECT COUNT(*) FROM results").fetchone()[0],
        "districts_available": len(DISTRICTS)
    }
    conn.close()
    return stats


# ============================================
# Background Job Runner
# ============================================
def run_cloud_job(job_id: str, district_code: str, survey_number: str):
    """Execute Cloud Run job"""
    try:
        # Update status
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE jobs SET status = 'running', started_at = ? WHERE job_id = ?",
                    (datetime.utcnow().isoformat(), job_id))
        conn.commit()
        conn.close()
        
        # Build env vars
        env_vars = f"DISTRICT_CODE={district_code}"
        if survey_number:
            env_vars += f",SURVEY_NUMBER={survey_number}"
        
        # Execute Cloud Run job
        cmd = [
            "gcloud", "run", "jobs", "execute", JOB_NAME,
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
            f"--update-env-vars={env_vars}",
            "--wait"  # Wait for completion
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode == 0:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                UPDATE jobs SET status = 'completed', completed_at = ? WHERE job_id = ?
            """, (datetime.utcnow().isoformat(), job_id))
            conn.commit()
            conn.close()
            print(f"[DONE] Job {job_id} completed")
        else:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                UPDATE jobs SET status = 'failed', error = ? WHERE job_id = ?
            """, (result.stderr[:500], job_id))
            conn.commit()
            conn.close()
            print(f"[ERROR] Job {job_id}: {result.stderr[:200]}")
            
    except Exception as e:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE jobs SET status = 'failed', error = ? WHERE job_id = ?",
                    (str(e)[:500], job_id))
        conn.commit()
        conn.close()
        print(f"[ERROR] Job {job_id}: {e}")


# ============================================
# Main
# ============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"\n🚀 AnyROR Dashboard running at http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
