import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from db_manager import DatabaseManager

class PersistenceManager:
    """
    Modular manager to handle 'Auto-Save & Resume' for any scraper.
    Ensures data safety on Spot VMs and across different project states.
    """
    
    def __init__(self, project_name: str, state_code: str = "GUJ", output_dir: str = "output"):
        self.project_name = project_name
        self.state_code = state_code
        self.base_output = output_dir
        self.live_dir = os.path.join(output_dir, "live_sync", state_code)
        self.db = DatabaseManager()
        
        # Ensure local directories exist
        os.makedirs(self.live_dir, exist_ok=True)
        
        # Set of completed task IDs for fast memory lookup
        self.completed_tasks = set()
        self._load_local_state()

    def _load_local_state(self):
        """Loads all task IDs from previously saved JSON files in the live sync directory."""
        if not os.path.exists(self.live_dir):
            return
            
        for filename in os.listdir(self.live_dir):
            if filename.endswith(".json"):
                # UUID/TaskID is usually the filename prefix
                task_id = filename.replace(".json", "")
                self.completed_tasks.add(task_id)
        
        print(f"[PERSISTENCE] Loaded {len(self.completed_tasks)} completed tasks from {self.live_dir}")

    def is_complete(self, task_id: str) -> bool:
        """Checks if a task (e.g., a specific village) has already been saved."""
        return task_id in self.completed_tasks

    async def save_result(self, task_id: str, data: Dict[str, Any], job_id: Optional[str] = None):
        """
        Saves record to both Local Disk and Database (Remote).
        Call this immediately after a successful scrape.
        """
        if not data:
            return False

        # 1. Save Locally (Emergency recovery)
        local_path = os.path.join(self.live_dir, f"{task_id}.json")
        try:
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump({
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                }, f, ensure_ascii=False, indent=2)
            self.completed_tasks.add(task_id)
        except Exception as e:
            print(f"[PERSISTENCE] Local save failed for {task_id}: {e}")

        # 2. Save to Database (Cloud Safety)
        # Using the existing DatabaseManager logic
        db_success = False
        try:
            await self.db.connect()
            
            # Use appropriate upsert based on the project/data type
            if "owners" in data or "owner_name" in data:
                # Handling owner records specifically if needed
                db_success = await self.db.upsert_owner_record_http(data)
            else:
                # Standard land record upsert
                db_success = await self.db.upsert_record(data, job_id=job_id)
                
            if db_success:
                print(f"[PERSISTENCE] ✓ {task_id} synced to Cloud")
        except Exception as e:
            print(f"[PERSISTENCE] Cloud sync failed for {task_id}: {e}")

        return True

    def get_summary(self) -> Dict:
        """Returns stats about the current run."""
        return {
            "project": self.project_name,
            "state": self.state_code,
            "completed_count": len(self.completed_tasks),
            "local_dir": self.live_dir
        }
