import os
import json
import asyncio
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from .db_manager import DatabaseManager

app = FastAPI(title="AnyROR Orchestrator")
db = DatabaseManager()

# Data Models
class ScrapeRequest(BaseModel):
    district_code: str
    taluka_codes: Optional[List[str]] = None
    owner_name: Optional[str] = None
    priority: int = 1

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.close()

def load_villages(district_code: str, taluka_codes: List[str] = None) -> List[dict]:
    """Helper to load village codes from the master JSON"""
    try:
        zone_file = "frontend/gujarat-anyror-complete.json"
        with open(zone_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        district = next((d for d in data["districts"] if d["value"] == district_code), None)
        if not district: return []
        
        villages = []
        for taluka in district["talukas"]:
            if taluka_codes and taluka["value"] not in taluka_codes:
                continue
            for v in taluka["villages"]:
                villages.append({
                    "district_code": district_code,
                    "taluka_code": taluka["value"],
                    "village_code": v["value"],
                    "village_name": v["label"]
                })
        return villages
    except Exception as e:
        print(f"[ORCH] Error loading villages: {e}")
        return []

@app.post("/jobs")
async def create_job(req: ScrapeRequest, background_tasks: BackgroundTasks):
    """Start a new district/taluka search job"""
    # 1. Register job
    job_id = await db.create_job(metadata={
        "district_code": req.district_code,
        "owner_name": req.owner_name
    })
    
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create job in DB")

    # 2. Decompose into tasks in background
    def decompose():
        villages = load_villages(req.district_code, req.taluka_codes)
        # We'll need a wrapper to run this async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(db.create_tasks_bulk(job_id, villages))
        loop.close()

    background_tasks.add_task(decompose)
    
    return {"job_id": job_id, "status": "initializing", "message": "Decomposing villages into tasks..."}

@app.get("/tasks/poll")
async def poll_task(worker_id: str):
    """
    Workers call this to get their next assignment.
    Finds one 'pending' task, locks it, and returns it.
    """
    # In a real system, we'd use a SELECT FOR UPDATE or similar
    # For now, we'll fetch one and update it
    if not db.pool: return {"status": "none"}
    
    async with db.pool.acquire() as conn:
        task = await conn.fetchrow("""
            UPDATE scrape_tasks 
            SET status = 'processing', locked_by = $1, locked_at = NOW(), attempts = attempts + 1
            WHERE id = (
                SELECT id FROM scrape_tasks 
                WHERE status = 'pending' 
                ORDER BY created_at ASC 
                LIMIT 1 
                FOR UPDATE SKIP LOCKED
            )
            RETURNING district_code, taluka_code, village_code, village_name, job_id
        """, worker_id)
        
        if not task:
            return {"status": "none"}
            
        # Get job metadata (owner name)
        owner_name = await conn.fetchval("SELECT (metadata->>'owner_name') FROM scrape_requests WHERE id = $1", task['job_id'])
        
        return {
            "status": "ok",
            "task_id": str(task['job_id']),
            "district_code": task['district_code'],
            "taluka_code": task['taluka_code'],
            "village_code": task['village_code'],
            "village_name": task['village_name'],
            "owner_name": owner_name
        }

@app.post("/tasks/{job_id}/{village_code}/complete")
async def complete_task(job_id: str, village_code: str, success: bool, error: str = None):
    """Worker reports completion status"""
    await db.update_task_status(job_id=job_id, village_code=village_code, status="completed" if success else "failed", error=error)
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy", "db": "connected" if db.pool else "disconnected"}
