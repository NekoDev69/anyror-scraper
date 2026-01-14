"""
Gujarat AnyROR Global Zone Search - Cloud Run API
Searches all talukas within a district for a given name/survey
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google.cloud import firestore
from google.cloud import tasks_v2

app = FastAPI(title="Gujarat AnyROR Global Search API")

# Config
PROJECT_ID = os.environ.get("GCP_PROJECT", "anyror-scraper")
REGION = os.environ.get("GCP_REGION", "asia-south1")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "scraper-queue")

# Load Gujarat data
with open("gujarat-anyror-complete.json", "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)

DISTRICTS = {d["value"]: d for d in GUJARAT_DATA["districts"]}

db = firestore.Client()


class SearchRequest(BaseModel):
    """Search request for global zone search"""
    district_code: str  # e.g., "01" for Kutch
    search_type: str = "survey"  # survey, owner_name, khata
    search_value: str  # survey number or name to search
    callback_url: Optional[str] = None


class DistrictSearchRequest(BaseModel):
    """Search all talukas in a district"""
    district_code: str
    search_type: str = "survey"
    search_value: str


@app.get("/")
def health():
    return {"status": "ok", "districts": len(DISTRICTS)}


@app.get("/districts")
def list_districts():
    """List all 34 districts"""
    return [
        {"code": d["value"], "name": d["label"], "talukas": len(d["talukas"])}
        for d in GUJARAT_DATA["districts"]
    ]


@app.get("/districts/{district_code}/talukas")
def list_talukas(district_code: str):
    """List all talukas in a district"""
    district = DISTRICTS.get(district_code)
    if not district:
        raise HTTPException(404, f"District {district_code} not found")
    
    return [
        {"code": t["value"], "name": t["label"], "villages": len(t["villages"])}
        for t in district["talukas"]
    ]


@app.post("/search/district")
async def search_district(req: DistrictSearchRequest, background_tasks: BackgroundTasks):
    """
    Trigger search across all talukas in a district
    Returns job_id to track progress
    """
    district = DISTRICTS.get(req.district_code)
    if not district:
        raise HTTPException(404, f"District {req.district_code} not found")
    
    # Create job record
    job_id = f"search_{req.district_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    job_doc = {
        "job_id": job_id,
        "district_code": req.district_code,
        "district_name": district["label"],
        "search_type": req.search_type,
        "search_value": req.search_value,
        "status": "queued",
        "total_talukas": len(district["talukas"]),
        "completed_talukas": 0,
        "results": [],
        "created_at": datetime.utcnow(),
    }
    
    db.collection("search_jobs").document(job_id).set(job_doc)
    
    # Queue tasks for each taluka
    background_tasks.add_task(queue_taluka_searches, job_id, district, req)
    
    return {
        "job_id": job_id,
        "status": "queued",
        "talukas_to_search": len(district["talukas"]),
        "message": f"Searching {district['label']} ({len(district['talukas'])} talukas)"
    }


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Get search job status and results"""
    doc = db.collection("search_jobs").document(job_id).get()
    if not doc.exists:
        raise HTTPException(404, "Job not found")
    
    return doc.to_dict()


@app.get("/jobs/{job_id}/results")
def get_job_results(job_id: str):
    """Get search results for a job"""
    doc = db.collection("search_jobs").document(job_id).get()
    if not doc.exists:
        raise HTTPException(404, "Job not found")
    
    data = doc.to_dict()
    return {
        "job_id": job_id,
        "status": data.get("status"),
        "total_results": len(data.get("results", [])),
        "results": data.get("results", [])
    }


async def queue_taluka_searches(job_id: str, district: dict, req: DistrictSearchRequest):
    """Queue Cloud Tasks for each taluka search"""
    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(PROJECT_ID, REGION, QUEUE_NAME)
        
        for taluka in district["talukas"]:
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"https://{REGION}-{PROJECT_ID}.cloudfunctions.net/scrape-taluka",
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "job_id": job_id,
                        "district_code": req.district_code,
                        "taluka_code": taluka["value"],
                        "taluka_name": taluka["label"],
                        "search_type": req.search_type,
                        "search_value": req.search_value,
                        "villages": taluka["villages"]
                    }).encode()
                }
            }
            client.create_task(request={"parent": parent, "task": task})
        
        # Update job status
        db.collection("search_jobs").document(job_id).update({
            "status": "processing"
        })
        
    except Exception as e:
        db.collection("search_jobs").document(job_id).update({
            "status": "error",
            "error": str(e)
        })


# For local testing without Cloud Tasks
@app.post("/search/taluka-direct")
async def search_taluka_direct(
    district_code: str,
    taluka_code: str,
    search_value: str,
    search_type: str = "survey"
):
    """Direct taluka search (for testing)"""
    from worker import TalukaScraper
    
    district = DISTRICTS.get(district_code)
    if not district:
        raise HTTPException(404, "District not found")
    
    taluka = next((t for t in district["talukas"] if t["value"] == taluka_code), None)
    if not taluka:
        raise HTTPException(404, "Taluka not found")
    
    scraper = TalukaScraper()
    results = await scraper.search_taluka(
        district_code=district_code,
        district_name=district["label"],
        taluka_code=taluka_code,
        taluka_name=taluka["label"],
        villages=taluka["villages"],
        search_type=search_type,
        search_value=search_value
    )
    
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
