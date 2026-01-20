import json
import os
import time
import threading
import concurrent.futures
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from anyror_scraper import AnyRORScraper
from src.db_manager import DatabaseManager
import asyncio

class GlobalOwnerScraper:
    """
    Orchestrates owner search across multiple talukas/districts
    with persistence and progress tracking.
    """
    
    def __init__(self, owner_name: str, district_code: str, headless: bool = True, num_workers: int = 2, taluka_codes: list = None):
        self.owner_name = owner_name
        self.district_code = district_code
        self.headless = headless
        self.num_workers = num_workers
        self.taluka_codes = taluka_codes # Optional filter
        
        # Setup persistence
        self.progress_file = f"owner_search_progress_{owner_name.replace(' ', '_')}_{district_code}.json"
        self.progress = self.load_progress()
        self.lock = threading.Lock()
        
        # Setup DB
        self.db = DatabaseManager()
        self.use_db = False
        
    def load_progress(self):
        """Load or initialize progress tracking"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "owner_name": self.owner_name,
            "district_code": self.district_code,
            "timestamp": datetime.now().isoformat(),
            "completed_villages": {}, # key: "taluka_code_village_code", value: results
            "hits": []
        }
        
    def save_progress(self):
        """Save current progress to file"""
        with self.lock:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2)
            
    def get_district_villages(self):
        """Get all villages in the target district"""
        # Load zone data directly here, as it's not thread-safe to share the file handle
        # or the mutable zone_data object across threads without explicit locking.
        # Loading it once per run is fine.
        with open("frontend/gujarat-anyror-complete.json", 'r', encoding='utf-8') as f:
            zone_data = json.load(f)

        district = next((d for d in zone_data["districts"] if d["value"] == self.district_code), None)
        if not district:
            raise ValueError(f"District {self.district_code} not found")
            
        talukas_data = []
        for t in district["talukas"]:
            talukas_data.append({
                "code": t["value"],
                "name": t["label"],
                "villages": [{"code": v["value"], "name": v["label"]} for v in t["villages"]]
            })
            
        # Apply taluka filter
        if self.taluka_codes:
            talukas_data = [t for t in talukas_data if t["code"] in self.taluka_codes]
            
        return talukas_data

    def process_taluka(self, taluka, t_idx, total_talukas):
        """Process a single taluka in a separate thread."""
        taluka_code = taluka["code"]
        taluka_name = taluka["name"]
        
        # Check pending villages in this taluka
        pending_villages = []
        with self.lock: # Acquire lock to safely read self.progress
            for v in taluka["villages"]:
                key = f"{taluka_code}_{v['code']}"
                if key not in self.progress["completed_villages"]:
                    pending_villages.append(v["code"])
        
        if not pending_villages:
            print(f"[{t_idx}/{total_talukas}] Skipping {taluka_name} - Already completed")
            return
            
        print(f"\n[{t_idx}/{total_talukas}] TALUKA: {taluka_name} ({len(pending_villages)} villages pending)")
        
        # Create a new scraper instance for this thread
        scraper = AnyRORScraper(headless=self.headless)
        try:
            scraper.start()
            
            def progress_callback(res):
                v_code = res["village_code"]
                key = f"{taluka_code}_{v_code}"
                
                with self.lock: # Acquire lock to safely modify self.progress
                    self.progress["completed_villages"][key] = {
                        "success": res["success"],
                        "count": res.get("count", 0),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    if res.get("matches"):
                        for match in res["matches"]:
                            hit = {
                                "taluka_name": taluka_name,
                                "taluka_code": taluka_code,
                                "village_code": v_code,
                                **match
                            }
                            # Avoid duplicates
                            if hit not in self.progress["hits"]:
                                self.progress["hits"].append(hit)
                                print(f"  [T:{taluka_name}] 🌟 HIT: {match['owner_name']} (Khata {match['khata_no']})")
                                
                                # Save to DB (Synchronous for production stability)
                                if self.use_db:
                                    self.db.upsert_owner_record_sync(hit)
                
                self.save_progress() # This also uses the lock internally

            # Use the new scraper method with callback
            scraper.scrape_owner_multiple_villages(
                district_code=self.district_code,
                taluka_code=taluka_code,
                village_codes=pending_villages,
                owner_name=self.owner_name,
                callback=progress_callback
            )
            
            print(f"✓ Completed {taluka_name}")
            
        except Exception as e:
            print(f"❌ Error in TALUKA {taluka_name}: {e}")
        finally:
            scraper.close()

    def run(self):
        """Execute the global search using a thread pool."""
        try:
            talukas = self.get_district_villages()
        except ValueError as e:
            print(f"[ERROR] {e}")
            return
            
        print(f"\n{'='*60}")
        print(f"TURBO GLOBAL OWNER SEARCH: '{self.owner_name}'")
        print(f"District: {self.district_code}")
        print(f"Workers: {self.num_workers} Parallel Talukas")
        print(f"Persistence File: {self.progress_file}")
        print(f"{'='*60}\n")
        
        # Initialize DB connection
        asyncio.run(self.db.connect())
        if self.db.pool:
            self.use_db = True
            print("[DB] 🔗 Direct PostgreSQL persistence ACTIVE")
        elif self.db.supabase_url and self.db.supabase_key:
            self.use_db = True
            print("[DB] 🚀 Supabase HTTP persistence ACTIVE (Direct pool failed/unavailable)")
        else:
            print("[DB] ⚠️ Supabase persistence INACTIVE (Using local JSON only)")
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = []
            for t_idx, taluka in enumerate(talukas, 1):
                futures.append(executor.submit(self.process_taluka, taluka, t_idx, len(talukas)))
            
            # Wait for all taluka processing to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result() # This will re-raise any exceptions from the worker threads
                except Exception as exc:
                    print(f"A taluka processing generated an exception: {exc}")

        print(f"\n{'='*60}")
        print("SEARCH COMPLETE")
        print(f"Total Hits: {len(self.progress['hits'])}")
        print(f"Progress stored in: {self.progress_file}")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Global Owner Search across districts/talukas")
    parser.add_argument("--name", required=True, help="Owner Name to search for")
    parser.add_argument("--district", default="07", help="District Code (default: 07 Ahmedabad)")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")
    parser.add_argument("--workers", type=int, default=2, help="Number of parallel talukas to process (default: 2)")
    parser.add_argument("--talukas", help="Comma-separated taluka codes to search (e.g. '01,02')")
    
    args = parser.parse_args()
    
    taluka_list = None
    if args.talukas:
        taluka_list = [t.strip() for t in args.talukas.split(",")]
    
    scraper = GlobalOwnerScraper(
        args.name, 
        args.district, 
        headless=args.headless, 
        num_workers=args.workers,
        taluka_codes=taluka_list
    )
    scraper.run()
