import os
import time
import httpx
import argparse
from anyror_scraper import AnyRORScraper
from .db_manager import DatabaseManager

class WorkerClient:
    def __init__(self, orchestrator_url: str, worker_id: str):
        self.orchestrator_url = orchestrator_url
        self.worker_id = worker_id
        self.db = DatabaseManager()
        
    def poll_and_execute(self):
        """Infinite loop to pull tasks and execute them"""
        print(f"[WORKER-{self.worker_id}] Starting polling loop...")
        
        while True:
            try:
                # 1. Ask orchestrator for work
                response = httpx.get(f"{self.orchestrator_url}/tasks/poll?worker_id={self.worker_id}")
                if response.status_code != 200:
                    print(f"[WORKER] Orchestrator error: {response.status_code}")
                    time.sleep(10)
                    continue
                
                task = response.json()
                if task.get("status") == "none":
                    print("[WORKER] No tasks available. Sleeping 15s...")
                    time.sleep(15)
                    continue
                
                # 2. Execute Scrape
                print(f"[WORKER] Received Task: {task['district_code']} - {task['village_code']}")
                self.execute_scrape(task)
                
            except Exception as e:
                print(f"[WORKER] Loop Exception: {e}")
                time.sleep(10)

    def execute_scrape(self, task: dict):
        """Initialize scraper and run the specific village task"""
        scraper = AnyRORScraper(headless=True)
        try:
            scraper.start()
            # Logic to run specific search based on task type
            # ... (integrated with anyror_scraper.py)
            
            # Report completion
            httpx.post(f"{self.orchestrator_url}/tasks/{task['village_code']}/complete", 
                        params={"worker_id": self.worker_id, "success": True})
            
        except Exception as e:
            print(f"[WORKER] Scrape failed: {e}")
            httpx.post(f"{self.orchestrator_url}/tasks/{task['village_code']}/complete", 
                        params={"worker_id": self.worker_id, "success": False, "error": str(e)})
        finally:
            scraper.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--id", default=f"node-{os.getpid()}")
    args = parser.parse_args()
    
    worker = WorkerClient(args.url, args.id)
    worker.poll_and_execute()
