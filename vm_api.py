"""
VM Backend API - Receives scraping jobs from frontend
Run with: uvicorn vm_api:app --host 0.0.0.0 --port 8000
"""

import os
import json
import uuid
import time
import threading
import zipfile
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="AnyROR Scraper API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job storage
jobs = {}
OUTPUT_DIR = "output"


class ScrapeRequest(BaseModel):
    district_code: str
    taluka_code: Optional[str] = None
    survey_filter: Optional[str] = None
    num_contexts: int = 4


class Job:
    def __init__(self, job_id: str, config: dict):
        self.job_id = job_id
        self.config = config
        self.status = "pending"
        self.total = 0
        self.done = 0
        self.success = 0
        self.start_time = None
        self.end_time = None
        self.logs = []
        self.results = []
        self.output_dir = f"{OUTPUT_DIR}/jobs/{job_id}"
        self.stop_requested = False
    
    def log(self, message: str, log_type: str = "info"):
        self.logs.append({
            "time": datetime.now().isoformat(),
            "message": message,
            "type": log_type
        })
        # Keep only last 100 logs
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]
    
    @property
    def rate(self):
        if not self.start_time or self.done == 0:
            return 0
        elapsed = time.time() - self.start_time
        return self.done / elapsed if elapsed > 0 else 0
    
    def to_dict(self):
        return {
            "job_id": self.job_id,
            "status": self.status,
            "total": self.total,
            "done": self.done,
            "success": self.success,
            "rate": self.rate,
            "recent_logs": self.logs[-10:],
            "download_url": f"/download/{self.job_id}" if self.status == "completed" else None
        }


def run_scraper(job: Job):
    """Run the scraper in background"""
    import subprocess
    import sys
    
    job.status = "running"
    job.start_time = time.time()
    job.log("Starting scraper...", "info")
    
    # Create job output directory
    os.makedirs(job.output_dir, exist_ok=True)
    os.makedirs(f"{job.output_dir}/raw", exist_ok=True)
    os.makedirs(f"{job.output_dir}/structured", exist_ok=True)
    os.makedirs(f"{job.output_dir}/reports", exist_ok=True)
    
    # Set environment
    env = os.environ.copy()
    env["DISTRICT_CODE"] = job.config["district_code"]
    env["TALUKA_CODE"] = job.config.get("taluka_code") or ""
    env["SURVEY_FILTER"] = job.config.get("survey_filter") or ""
    env["NUM_CONTEXTS"] = str(job.config.get("num_contexts", 4))
    env["OUTPUT_DIR"] = job.output_dir
    env["JOB_ID"] = job.job_id
    
    try:
        # Run scraper as subprocess
        process = subprocess.Popen(
            [sys.executable, "vm_bulk_scraper_api.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Read output in real-time
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            
            # Parse progress updates
            if line.startswith("PROGRESS:"):
                parts = line.split(":")
                if len(parts) >= 4:
                    job.total = int(parts[1])
                    job.done = int(parts[2])
                    job.success = int(parts[3])
            elif line.startswith("LOG:"):
                msg = line[4:]
                log_type = "info"
                if "✅" in msg:
                    log_type = "success"
                elif "❌" in msg:
                    log_type = "error"
                job.log(msg, log_type)
            else:
                job.log(line, "info")
            
            # Check stop request
            if job.stop_requested:
                process.terminate()
                job.log("Stopped by user", "error")
                break
        
        process.wait()
        
        if job.stop_requested:
            job.status = "stopped"
        elif process.returncode == 0:
            job.status = "completed"
            job.log(f"Completed: {job.success}/{job.total} successful", "success")
            create_download_zip(job)
        else:
            job.status = "failed"
            job.log(f"Failed with code {process.returncode}", "error")
            
    except Exception as e:
        job.status = "failed"
        job.log(f"Error: {str(e)}", "error")
    
    job.end_time = time.time()


def create_download_zip(job: Job):
    """Create zip file of results"""
    zip_path = f"{job.output_dir}/results.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for folder in ['raw', 'structured', 'reports']:
            folder_path = f"{job.output_dir}/{folder}"
            if os.path.exists(folder_path):
                for file in os.listdir(folder_path):
                    file_path = f"{folder_path}/{file}"
                    zf.write(file_path, f"{folder}/{file}")
    
    job.log(f"Download ready: results.zip", "success")


@app.get("/")
def root():
    return {"status": "ok", "service": "AnyROR Scraper API"}


@app.post("/start")
def start_job(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Start a new scraping job"""
    job_id = str(uuid.uuid4())[:8]
    
    job = Job(job_id, request.dict())
    jobs[job_id] = job
    
    # Start scraper in background
    background_tasks.add_task(run_scraper, job)
    
    return {"job_id": job_id, "status": "started"}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id].to_dict()


@app.post("/stop/{job_id}")
def stop_job(job_id: str):
    """Stop a running job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    jobs[job_id].stop_requested = True
    return {"status": "stop_requested"}


@app.get("/download/{job_id}")
def download_results(job_id: str):
    """Download job results"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    zip_path = f"{job.output_dir}/results.zip"
    
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Results not ready")
    
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"anyror_results_{job_id}.zip"
    )


@app.get("/jobs")
def list_jobs():
    """List all jobs"""
    return {
        "jobs": [j.to_dict() for j in jobs.values()]
    }


if __name__ == "__main__":
    import uvicorn
    os.makedirs(f"{OUTPUT_DIR}/jobs", exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
