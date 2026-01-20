# Implementation Plan: High-Performance District Scraper

## Overview

This implementation plan breaks down the high-performance district scraper into discrete coding tasks. The system will be built incrementally, starting with core components (rate limiter, queue, progress tracker), then worker management, and finally the main orchestrator. Each task builds on previous work and includes testing sub-tasks.

## Tasks

- [x] 1. Implement CaptchaRateLimiter with sliding window algorithm
  - Create async rate limiter class with configurable RPM
  - Implement sliding window tracking (remove requests older than 60s)
  - Implement acquire() method that blocks when limit reached
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 1.1 Write property test for CaptchaRateLimiter
  - **Property 13: Captcha Rate Limit Enforcement**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
  - Test that no 60-second window exceeds max_rpm
  - Test concurrent access from multiple workers

- [x] 2. Implement VillageQueue for thread-safe work distribution
  - Create async queue class with village list initialization
  - Implement get_next() method with async lock
  - Implement size() method for queue monitoring
  - _Requirements: 2.5, 5.4_

- [x] 2.1 Write property test for VillageQueue
  - **Property 9: Even Work Distribution**
  - **Validates: Requirements 2.5, 5.4**
  - Test that villages are distributed evenly across workers
  - Test concurrent get_next() calls

- [x] 3. Implement ProgressTracker with atomic counters
  - Create progress tracker class with total_villages initialization
  - Implement atomic increment methods (processed, successful, failed)
  - Implement get_stats() method with percentage and rate calculation
  - Implement print_progress() method with formatted output
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 3.1 Write property tests for ProgressTracker
  - **Property 14: Counter Accuracy**
  - **Validates: Requirements 8.1**
  - Test that successful + failed = processed
  - **Property 15: Atomic Counter Updates**
  - **Validates: Requirements 8.2**
  - Test concurrent updates don't cause race conditions
  - **Property 16: Progress Calculation Accuracy**
  - **Validates: Requirements 8.3, 8.4**
  - Test percentage and throughput calculations

- [x] 4. Implement Worker class with session management
  - Create Worker class with context_id, tab_id, page, rate_limiter, captcha_solver, extractor
  - Implement setup_session() method to navigate and select district/taluka
  - Implement navigate_back_to_form() method using "RURAL LAND RECORD" link
  - Implement helper methods: get_captcha_image(), solve_captcha(), extract_data()
  - _Requirements: 1.5, 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4.1 Write property tests for Worker session management
  - **Property 10: Session State Preservation**
  - **Validates: Requirements 1.5, 3.1, 3.2, 3.3**
  - Test that navigate_back_to_form() preserves district/taluka
  - **Property 12: Session Restoration**
  - **Validates: Requirements 3.5**
  - Test that setup_session() restores correct selections

- [x] 5. Implement Worker.process_village() with error recovery
  - Implement process_village() method with village_code parameter
  - Add captcha retry loop (max 3 attempts)
  - Add session recovery logic (navigate_back_to_form fallback)
  - Return VillageResult with success status and data
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 10.1_

- [x] 5.1 Write property tests for Worker error recovery
  - **Property 11: Session Recovery Fallback**
  - **Validates: Requirements 3.4, 9.3**
  - Test that failed navigate_back_to_form() triggers setup_session()
  - **Property 19: Graceful Error Recovery**
  - **Validates: Requirements 9.2, 9.4**
  - Test that errors mark village as failed and continue

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement WorkerPool for managing contexts and tabs
  - Create WorkerPool class with browser, num_contexts, tabs_per_context, rate_limiter
  - Implement create_workers() method to spawn all contexts and tabs
  - Implement close_all() method to cleanup contexts
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 7.1 Write property test for WorkerPool
  - **Property 3: Worker Pool Size**
  - **Validates: Requirements 1.3, 5.2, 5.3**
  - Test that num_contexts × tabs_per_context workers are created

- [x] 8. Implement data loading utilities
  - Create load_district_data() function to read gujarat-anyror-complete.json
  - Create get_district() function to find district by code
  - Create get_taluka() function to find taluka by code
  - Create get_villages() function to extract village list
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 8.1 Write property tests for data loading
  - **Property 6: District Data Loading**
  - **Validates: Requirements 2.2**
  - Test that all valid district codes load successfully
  - **Property 7: Taluka Data Loading**
  - **Validates: Requirements 2.3**
  - Test that all valid taluka codes load successfully
  - **Property 8: Full District Processing**
  - **Validates: Requirements 2.4**
  - Test that None taluka_code loads all talukas

- [x] 9. Implement ScraperConfig dataclass
  - Create ScraperConfig dataclass with all configuration fields
  - Add default values matching design specification
  - Add from_env() class method to load from environment variables
  - _Requirements: 5.1, 6.1, 6.3, 7.2_

- [x] 9.1 Write property test for environment variable configuration
  - **Property 5: Environment Variable Configuration**
  - **Validates: Requirements 7.2**
  - Test that env vars override defaults

- [x] 10. Implement result storage functions
  - Create save_village_result() function to save raw and structured data
  - Create generate_summary_report() function to create summary JSON
  - Implement unique filename generation with timestamps
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 7.3, 7.4_

- [x] 10.1 Write property tests for result storage
  - **Property 22: Complete Result File Structure**
  - **Validates: Requirements 10.2, 10.3, 10.5**
  - Test that saved files contain all required fields
  - **Property 23: Summary Report Generation**
  - **Validates: Requirements 6.5, 7.3, 7.4, 10.4**
  - Test that summary contains metadata and results
  - **Property 24: Output Directory Persistence**
  - **Validates: Requirements 7.3**
  - Test that all files are saved in output_dir

- [x] 11. Implement HighPerformanceDistrictScraper main orchestrator
  - Create HighPerformanceDistrictScraper class with config parameter
  - Implement __init__() to initialize components (rate_limiter, progress_tracker, etc.)
  - Implement _distribute_villages() method to create village queue
  - Implement _run_worker() async method for worker execution loop
  - _Requirements: 1.1, 1.2, 1.3, 2.5, 5.4_

- [ ] 12. Implement HighPerformanceDistrictScraper.scrape_district() method
  - Load district/taluka data and create village list
  - Apply max_villages limit if specified
  - Create browser and worker pool
  - Spawn worker tasks and await completion
  - Collect results and generate summary
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.1, 6.2_

- [ ] 12.1 Write property test for village limit enforcement
  - **Property 4: Village Limit Enforcement**
  - **Validates: Requirements 6.2**
  - Test that max_villages limits processing

- [ ] 13. Add error logging throughout the system
  - Add structured logging to Worker with village context
  - Add error logging to HighPerformanceDistrictScraper
  - Ensure all errors include timestamps and context
  - _Requirements: 9.1, 7.5_

- [x] 13.1 Write property tests for error logging
  - **Property 18: Error Logging with Context**
  - **Validates: Requirements 9.1, 7.5**
  - Test that error logs include village_code and worker_id
  - **Property 20: Failed Village Reporting**
  - **Validates: Requirements 9.5**
  - Test that failed villages appear in final report

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [-] 15. Create local testing script
  - Create test_local_performance.py script
  - Configure for small-scale test (10 villages, 2 contexts, 2 tabs)
  - Add throughput measurement and reporting
  - Add result validation
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 15.1 Write integration test for local small-scale scraping
  - Test scraping 10 villages with 2×2 workers
  - Verify all villages processed
  - Verify results saved correctly
  - **Property 1: Throughput Target**
  - **Validates: Requirements 1.1, 1.2**
  - Measure and verify throughput ≥ 40 villages/minute

- [ ] 16. Create GCP deployment script
  - Create deploy_gcp.sh script for VM setup
  - Add environment variable configuration
  - Add systemd service file for background execution
  - Add log rotation configuration
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 16.1 Integrate VF7Extractor and VF7ReportGenerator for post-processing
  - Add post-processing step after scraping completes
  - Generate structured JSON for all successful scrapes
  - Generate HTML reports for all successful scrapes
  - Save to output/raw/, output/structured/, output/reports/ directories
  - _Requirements: 10.1, 10.2, 10.4_

- [ ] 17. Create main entry point script
  - Create high_performance_scraper.py main script
  - Add command-line argument parsing (district, taluka, max_villages, etc.)
  - Add configuration loading from env vars
  - Add execution with error handling
  - _Requirements: 2.1, 6.1, 7.2_

- [ ] 18. Final integration test - 50 village performance test
  - Test scraping 50 villages with 5×5 workers
  - Measure actual throughput
  - Verify session reuse is working (check logs)
  - Verify rate limiting is working (check captcha request times)
  - _Requirements: 1.1, 1.2, 1.5, 4.1_

- [ ] 18.1 Write performance property test
  - **Property 1: Throughput Target**
  - **Validates: Requirements 1.1, 1.2**
  - Test that throughput ≥ 40 villages/minute for 50+ villages
  - **Property 2: Completion Time Bound**
  - **Validates: Requirements 1.1**
  - Test that 500 villages complete in ≤ 12 minutes

- [ ] 19. Documentation and README
  - Create README.md with setup instructions
  - Document configuration options
  - Add usage examples for local and GCP
  - Add troubleshooting section
  - _Requirements: All_

- [ ] 20. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Integration tests validate end-to-end workflows
- The implementation follows an incremental approach: core components → workers → orchestrator → deployment
- Session reuse optimization is critical for performance - verify it's working in integration tests
