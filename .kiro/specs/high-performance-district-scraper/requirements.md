# Requirements Document

## Introduction

This specification defines a high-performance web scraping system for the Gujarat AnyROR portal that can scrape 500 villages in 10 minutes (50 villages/minute) using district-wise searches. The system will be tested locally first, then deployed to a GCP VM for production use.

## Glossary

- **System**: The high-performance AnyROR scraper
- **Village**: A geographic administrative unit in Gujarat with land records
- **District**: A collection of talukas (administrative divisions)
- **Taluka**: A collection of villages within a district
- **Captcha_Solver**: AI-powered service that solves captcha challenges
- **Worker**: A browser tab/page that processes villages independently
- **Context**: A browser context containing multiple worker tabs
- **Session_Reuse**: Technique where district/taluka selections are preserved between village scrapes
- **Rate_Limiter**: Component that controls captcha API request frequency
- **Parallel_Scraper**: System that coordinates multiple workers across contexts

## Requirements

### Requirement 1: High-Performance Parallel Scraping

**User Story:** As a data collector, I want to scrape 500 villages in 10 minutes, so that I can efficiently collect land records at scale.

#### Acceptance Criteria

1. WHEN scraping 500 villages, THE System SHALL complete within 10 minutes (600 seconds)
2. WHEN processing villages, THE System SHALL achieve a minimum throughput of 50 villages per minute
3. WHEN running locally, THE System SHALL use configurable parallelism (contexts and tabs per context)
4. WHEN deployed on GCP VM, THE System SHALL scale to handle district-level workloads
5. WHEN processing villages in parallel, THE System SHALL maintain session state per worker to avoid re-navigation overhead

### Requirement 2: District-Wise Search Strategy

**User Story:** As a data collector, I want to scrape villages by district and taluka, so that I can organize data collection geographically.

#### Acceptance Criteria

1. WHEN starting a scrape job, THE System SHALL accept district code and taluka code as input parameters
2. WHEN a district code is provided, THE System SHALL load all talukas within that district
3. WHEN a taluka code is provided, THE System SHALL load all villages within that taluka
4. WHEN no taluka code is provided, THE System SHALL process all talukas in the district sequentially
5. WHEN processing a taluka, THE System SHALL distribute villages across available workers

### Requirement 3: Session Reuse Optimization

**User Story:** As a system architect, I want to reuse browser sessions between village scrapes, so that I can minimize navigation overhead and maximize throughput.

#### Acceptance Criteria

1. WHEN a worker completes a village scrape, THE System SHALL navigate back to the form using the "RURAL LAND RECORD" link
2. WHEN navigating back to the form, THE System SHALL preserve district and taluka selections
3. WHEN district and taluka are preserved, THE System SHALL only need to change the village dropdown
4. WHEN session reuse fails, THE System SHALL fall back to full re-navigation
5. WHEN re-navigating, THE System SHALL restore district and taluka selections

### Requirement 4: Captcha Rate Limiting

**User Story:** As a system operator, I want to control captcha API request rates, so that I can avoid quota violations and API throttling.

#### Acceptance Criteria

1. WHEN making captcha requests, THE System SHALL enforce a configurable maximum requests per minute (RPM)
2. WHEN the RPM limit is reached, THE System SHALL queue additional requests and wait
3. WHEN a captcha slot becomes available, THE System SHALL process the next queued request
4. WHEN tracking request times, THE System SHALL use a sliding window of 60 seconds
5. WHEN configured with 8 RPM, THE System SHALL not exceed 8 captcha requests in any 60-second window

### Requirement 5: Worker Pool Management

**User Story:** As a system architect, I want to manage multiple browser contexts and tabs, so that I can maximize parallelism while controlling resource usage.

#### Acceptance Criteria

1. WHEN initializing the System, THE System SHALL accept num_contexts and tabs_per_context as configuration
2. WHEN starting workers, THE System SHALL create num_contexts browser contexts
3. WHEN creating a context, THE System SHALL create tabs_per_context pages within that context
4. WHEN distributing work, THE System SHALL assign villages evenly across all workers
5. WHEN a worker completes its queue, THE System SHALL allow that worker to terminate

### Requirement 6: Local Testing Mode

**User Story:** As a developer, I want to test the scraper locally with a small village subset, so that I can validate performance before deploying to GCP.

#### Acceptance Criteria

1. WHEN running in local mode, THE System SHALL accept a max_villages parameter to limit the test size
2. WHEN max_villages is set, THE System SHALL only process the first N villages from the taluka
3. WHEN running locally, THE System SHALL support non-headless mode for debugging
4. WHEN testing locally, THE System SHALL measure and report throughput (villages/minute)
5. WHEN local testing completes, THE System SHALL save results to a timestamped JSON file

### Requirement 7: GCP VM Deployment

**User Story:** As a system operator, I want to deploy the scraper to a GCP VM, so that I can run large-scale scraping jobs in the cloud.

#### Acceptance Criteria

1. WHEN deploying to GCP, THE System SHALL run in headless mode
2. WHEN running on GCP, THE System SHALL accept environment variables for configuration
3. WHEN processing on GCP, THE System SHALL save results to a persistent output directory
4. WHEN a job completes on GCP, THE System SHALL generate a summary report with statistics
5. WHEN errors occur on GCP, THE System SHALL log errors with timestamps and context

### Requirement 8: Progress Tracking and Reporting

**User Story:** As a system operator, I want to track scraping progress in real-time, so that I can monitor job status and estimate completion time.

#### Acceptance Criteria

1. WHEN processing villages, THE System SHALL maintain counters for total, processed, successful, and failed
2. WHEN a village completes, THE System SHALL update progress counters atomically
3. WHEN progress updates, THE System SHALL calculate and display percentage complete
4. WHEN progress updates, THE System SHALL calculate and display current throughput (villages/minute)
5. WHEN the job completes, THE System SHALL display final statistics including success rate and total duration

### Requirement 9: Error Handling and Recovery

**User Story:** As a system operator, I want the scraper to handle errors gracefully, so that individual failures don't crash the entire job.

#### Acceptance Criteria

1. WHEN a worker encounters an error, THE System SHALL log the error with village context
2. WHEN a worker error occurs, THE System SHALL mark that village as failed and continue
3. WHEN session reuse fails, THE System SHALL attempt full re-navigation
4. WHEN re-navigation fails, THE System SHALL mark the village as failed and continue
5. WHEN all workers complete, THE System SHALL include failed villages in the final report

### Requirement 10: Result Storage and Extraction

**User Story:** As a data analyst, I want scraping results saved in structured format, so that I can analyze land records efficiently.

#### Acceptance Criteria

1. WHEN a village scrape succeeds, THE System SHALL extract structured data using VF7Extractor
2. WHEN saving results, THE System SHALL save both raw and structured formats
3. WHEN saving files, THE System SHALL use unique filenames with timestamps
4. WHEN a job completes, THE System SHALL save a summary JSON with metadata and all results
5. WHEN results are saved, THE System SHALL include district, taluka, and village identifiers
