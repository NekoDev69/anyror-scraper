-- Database Schema for AnyROR Scraper

-- 1. Scrape Requests Table
-- Tracks who initiated the job and its status
CREATE TABLE IF NOT EXISTS scrape_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(50) DEFAULT 'processing', -- pending, processing, completed, failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB -- store extra info like user_id, district_name, etc.
);

-- 2. Land Records Table
-- Stores the actual scraped data
CREATE TABLE IF NOT EXISTS land_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Indexed fields for fast lookup
    district_code VARCHAR(10) NOT NULL,
    taluka_code VARCHAR(10) NOT NULL,
    village_code VARCHAR(10) NOT NULL,
    survey_number VARCHAR(50) NOT NULL,
    
    -- The core data (JSONB allows schema flexibility if Gujarat Gov changes format)
    record_data JSONB NOT NULL,
    
    -- Job tracking
    request_id UUID REFERENCES scrape_requests(id),
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Prevent duplicates: A survey in a village is unique.
    -- If we scrape it again, we update the existing row.
    UNIQUE (district_code, taluka_code, village_code, survey_number)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_land_records_location 
ON land_records (district_code, taluka_code, village_code);

CREATE INDEX IF NOT EXISTS idx_land_records_request 
ON land_records (request_id);

-- 3. Scrape Tasks / Queue Table
-- Tracks the specific status of every village to be scraped.
-- Enables "Resume from Crash" functionality.
CREATE TABLE IF NOT EXISTS scrape_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES scrape_requests(id),
    
    -- Task Scope
    district_code VARCHAR(10),
    taluka_code VARCHAR(10),
    village_code VARCHAR(10),
    village_name VARCHAR(100),
    
    -- State
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    attempts INT DEFAULT 0,
    locked_by VARCHAR(50), -- Worker ID / Hostname
    locked_at TIMESTAMP WITH TIME ZONE,
    
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    
    -- Constraint: A village appears once per job
    UNIQUE(job_id, village_code)
);

CREATE INDEX IF NOT EXISTS idx_scrape_tasks_status 
ON scrape_tasks (status, job_id);
