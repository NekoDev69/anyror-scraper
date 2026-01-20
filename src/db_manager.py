import os
import json
import asyncio
import asyncpg
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
from datetime import datetime
from typing import Dict, Optional, Any
from dotenv import load_dotenv

class DatabaseManager:
    """
    Native GCP Database Manager for AnyROR Scraper.
    Supports Cloud SQL (PostgreSQL) for state/queue and BigQuery for analytics.
    """
    def __init__(self):
        load_dotenv()
        self.pool: Optional[asyncpg.Pool] = None
        
        # Connection string: postgres://user:pass@host:port/db
        self.db_url = os.getenv("DATABASE_URL")
        
        if not self.db_url:
            print("[DB] ⚠️ DATABASE_URL not found in .env. Running in Mock Mode.")
            
    async def connect(self):
        """Create asyncpg connection pool for Cloud SQL / Postgres"""
        if self.db_url and not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    self.db_url,
                    min_size=2,
                    max_size=20
                )
                print("[DB] ✓ Connected to Cloud SQL (PostgreSQL)")
            except Exception as e:
                print(f"[DB] ❌ Connection failed: {e}")
                self.pool = None

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            print("[DB] Connection closed")

    async def create_job(self, metadata: Dict = None) -> Optional[str]:
        """Create a new scrape request entry"""
        if not self.pool: return None
        try:
            async with self.pool.acquire() as conn:
                job_id = await conn.fetchval("""
                    INSERT INTO scrape_requests (status, metadata)
                    VALUES ($1, $2)
                    RETURNING id
                """, 'processing', json.dumps(metadata or {}))
                return str(job_id)
        except Exception as e:
            print(f"[DB] Failed to create job: {e}")
            return None

    async def complete_job(self, job_id: str, status: str = 'completed'):
        """Mark job as complete/failed"""
        if not self.pool or not job_id: return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE scrape_requests 
                    SET status = $1, updated_at = NOW()
                    WHERE id = $2
                """, status, job_id)
        except Exception as e:
            print(f"[DB] Failed to close job: {e}")

    async def upsert_record(self, record: Dict, job_id: str = None) -> bool:
        """Insert or Update a land record"""
        if not self.pool: return False
        try:
            district = record["district"]["value"]
            taluka = record["taluka"]["value"]
            village = record["village"]["value"]
            survey = record["survey"]["value"]
            record_json = json.dumps(record)
            
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO land_records 
                    (district_code, taluka_code, village_code, survey_number, record_data, request_id, scraped_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (district_code, taluka_code, village_code, survey_number)
                    DO UPDATE SET 
                        record_data = EXCLUDED.record_data,
                        request_id = EXCLUDED.request_id,
                        scraped_at = NOW()
                """, district, taluka, village, survey, record_json, job_id)
                return True
        except Exception as e:
            print(f"[DB] Failed to upsert record: {e}")
            return False

    def upsert_owner_record_sync(self, hit: Dict) -> bool:
        """
        Synchronous upsert for Postgres.
        Used by threaded scrapers to avoid event loop conflicts.
        """
        if not self.db_url: return False
        if not PSYCOPG2_AVAILABLE:
            print("[DB] ❌ psycopg2 not installed. Sync upsert failed.")
            return False
            
        try:
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO land_records_owner 
                        (district_code, taluka_code, village_code, taluka_name, khata_no, survey_no, owner_name, scraped_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (district_code, taluka_code, village_code, khata_no, owner_name)
                        DO NOTHING
                    """, (
                        hit.get("district_code", "01"),
                        hit.get("taluka_code"),
                        hit.get("village_code"),
                        hit.get("taluka_name"),
                        hit.get("khata_no"),
                        hit.get("survey_no"),
                        hit.get("owner_name")
                    ))
                conn.commit()
                return True
        except Exception as e:
            print(f"[DB-SYNC] ❌ Postgres Upsert Error: {e}")
            return False

    async def create_tasks_bulk(self, job_id: str, villages: list):
        """Insert all villages as pending tasks"""
        if not self.pool: return
        tasks_data = [
            (job_id, v["district_code"], v["taluka_code"], v["village_code"], v["village_name"], 'pending')
            for v in villages
        ]
        try:
            async with self.pool.acquire() as conn:
                await conn.executemany("""
                    INSERT INTO scrape_tasks 
                    (job_id, district_code, taluka_code, village_code, village_name, status)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (job_id, village_code) DO NOTHING
                """, tasks_data)
        except Exception as e:
            print(f"[DB] Failed to bulk insert tasks: {e}")

    async def get_pending_tasks(self, job_id: str) -> list:
        """Fetch incomplete tasks"""
        if not self.pool: return []
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT taluka_code, village_code, village_name
                    FROM scrape_tasks 
                    WHERE job_id = $1 AND status != 'completed'
                    ORDER BY taluka_code, village_code
                """, job_id)
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"[DB] Failed to get pending tasks: {e}")
            return []

    async def update_task_status(self, job_id: str, village_code: str, status: str, error: str = None):
        """Mark task status"""
        if not self.pool or not job_id: return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE scrape_tasks 
                    SET status = $1, completed_at = NOW(), last_error = $2
                    WHERE job_id = $3 AND village_code = $4
                """, status, error, job_id, village_code)
        except Exception as e:
            print(f"[DB] Failed to update task status: {e}")
