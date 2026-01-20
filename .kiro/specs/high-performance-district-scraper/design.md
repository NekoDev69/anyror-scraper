# Design Document: High-Performance District Scraper

## Overview

This design describes a high-performance web scraping system for the Gujarat AnyROR portal that achieves 50 villages/minute throughput (500 villages in 10 minutes) through aggressive parallelization and session reuse optimization.

The system uses an async architecture with multiple browser contexts (each containing multiple tabs) to maximize concurrency while respecting captcha API rate limits. The key innovation is session reuse: after scraping a village, workers navigate back to the form (preserving district/taluka selections) rather than starting fresh, reducing overhead by ~80%.

The design supports both local testing (with configurable parallelism and village limits) and GCP VM deployment (with environment-based configuration and persistent storage).

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                   HighPerformanceDistrictScraper            │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Context 1  │  │   Context 2  │  │   Context N  │    │
│  │              │  │              │  │              │    │
│  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │    │
│  │  │ Tab 1  │  │  │  │ Tab 1  │  │  │  │ Tab 1  │  │    │
│  │  ├────────┤  │  │  ├────────┤  │  │  ├────────┤  │    │
│  │  │ Tab 2  │  │  │  │ Tab 2  │  │  │  │ Tab 2  │  │    │
│  │  ├────────┤  │  │  ├────────┤  │  │  ├────────┤  │    │
│  │  │ Tab M  │  │  │  │ Tab M  │  │  │  │ Tab M  │  │    │
│  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           CaptchaRateLimiter (8 RPM)                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           VillageQueue (Thread-Safe)                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           ProgressTracker (Atomic Counters)          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Execution Flow

1. **Initialization**: Load district/taluka data, create village queue
2. **Worker Creation**: Spawn N contexts × M tabs = N×M workers
3. **Session Setup**: Each worker navigates to portal, selects district/taluka
4. **Village Processing**: Workers pull from queue, scrape, navigate back (session reuse)
5. **Rate Limiting**: Captcha requests throttled to 8 RPM across all workers
6. **Result Collection**: Successful scrapes saved to output directory
7. **Completion**: Generate summary report with statistics

### Performance Model

Target: 500 villages in 10 minutes = 50 villages/minute

With 10 contexts × 5 tabs = 50 workers:
- Each worker needs to process 10 villages in 10 minutes
- 1 village per minute per worker
- Average 60 seconds per village (including captcha retries)

Breakdown per village:
- Session reuse navigation: ~2s (vs ~10s fresh navigation)
- Village/survey selection: ~3s
- Captcha solving (1-3 attempts): ~15-45s
- Data extraction: ~2s
- Total: ~22-52s per village (avg ~37s)

With 50 workers and session reuse, theoretical max: ~81 villages/minute
Target of 50 villages/minute provides 38% safety margin for retries and errors.

## Components and Interfaces

### HighPerformanceDistrictScraper

Main orchestrator class that manages the entire scraping operation.

```python
class HighPerformanceDistrictScraper:
    def __init__(
        self,
        num_contexts: int = 10,
        tabs_per_context: int = 5,
        max_captcha_rpm: int = 8,
        headless: bool = True
    ):
        """
        Initialize high-performance scraper.
        
        Args:
            num_contexts: Number of browser contexts (default 10)
            tabs_per_context: Number of tabs per context (default 5)
            max_captcha_rpm: Max captcha requests per minute (default 8)
            headless: Run browsers in headless mode (default True)
        """
        
    async def scrape_district(
        self,
        district_code: str,
        taluka_code: str = None,
        max_villages: int = None,
        output_dir: str = "output"
    ) -> dict:
        """
        Scrape villages from a district/taluka.
        
        Args:
            district_code: District value code (e.g., "02")
            taluka_code: Optional taluka code (if None, scrapes all talukas)
            max_villages: Optional limit for testing (if None, scrapes all)
            output_dir: Directory for results
            
        Returns:
            Summary dict with statistics and file paths
        """
```

### CaptchaRateLimiter

Async rate limiter that enforces maximum captcha requests per minute.

```python
class CaptchaRateLimiter:
    def __init__(self, max_rpm: int = 8):
        """
        Initialize rate limiter.
        
        Args:
            max_rpm: Maximum requests per minute
        """
        
    async def acquire(self) -> None:
        """
        Acquire a rate limit slot.
        Blocks if RPM limit reached until a slot becomes available.
        Uses sliding window algorithm.
        """
```

### WorkerPool

Manages browser contexts and worker tabs.

```python
class WorkerPool:
    def __init__(
        self,
        browser: Browser,
        num_contexts: int,
        tabs_per_context: int,
        captcha_rate_limiter: CaptchaRateLimiter
    ):
        """
        Initialize worker pool.
        
        Args:
            browser: Playwright browser instance
            num_contexts: Number of contexts to create
            tabs_per_context: Number of tabs per context
            captcha_rate_limiter: Shared rate limiter
        """
        
    async def create_workers(self) -> list[Worker]:
        """
        Create all worker instances.
        
        Returns:
            List of Worker objects
        """
        
    async def close_all(self) -> None:
        """
        Close all contexts and workers.
        """
```

### Worker

Individual worker that processes villages from a queue.

```python
class Worker:
    def __init__(
        self,
        context_id: int,
        tab_id: int,
        page: Page,
        captcha_rate_limiter: CaptchaRateLimiter,
        captcha_solver: CaptchaSolver,
        extractor: VF7Extractor
    ):
        """
        Initialize worker.
        
        Args:
            context_id: Context identifier
            tab_id: Tab identifier within context
            page: Playwright page instance
            captcha_rate_limiter: Shared rate limiter
            captcha_solver: Captcha solving service
            extractor: Data extraction service
        """
        
    async def setup_session(
        self,
        district_code: str,
        taluka_code: str
    ) -> bool:
        """
        Navigate to portal and select district/taluka.
        
        Args:
            district_code: District value code
            taluka_code: Taluka value code
            
        Returns:
            True if setup successful, False otherwise
        """
        
    async def process_village(
        self,
        village_code: str,
        max_captcha_attempts: int = 3
    ) -> dict:
        """
        Process a single village.
        Uses session reuse - assumes district/taluka already selected.
        
        Args:
            village_code: Village value code
            max_captcha_attempts: Max captcha retry attempts
            
        Returns:
            Result dict with success status and data
        """
        
    async def navigate_back_to_form(self) -> bool:
        """
        Navigate back to form using "RURAL LAND RECORD" link.
        Preserves district/taluka selections.
        
        Returns:
            True if navigation successful, False otherwise
        """
```

### VillageQueue

Thread-safe queue for distributing villages across workers.

```python
class VillageQueue:
    def __init__(self, villages: list[dict]):
        """
        Initialize village queue.
        
        Args:
            villages: List of village dicts with 'value' and 'label' keys
        """
        
    async def get_next(self) -> dict | None:
        """
        Get next village from queue.
        
        Returns:
            Village dict or None if queue empty
        """
        
    def size(self) -> int:
        """
        Get current queue size.
        
        Returns:
            Number of villages remaining
        """
```

### ProgressTracker

Thread-safe progress tracking with atomic counters.

```python
class ProgressTracker:
    def __init__(self, total_villages: int):
        """
        Initialize progress tracker.
        
        Args:
            total_villages: Total number of villages to process
        """
        
    async def increment_processed(self) -> None:
        """
        Increment processed counter atomically.
        """
        
    async def increment_successful(self) -> None:
        """
        Increment successful counter atomically.
        """
        
    async def increment_failed(self) -> None:
        """
        Increment failed counter atomically.
        """
        
    def get_stats(self) -> dict:
        """
        Get current statistics.
        
        Returns:
            Dict with total, processed, successful, failed, percentage, rate
        """
        
    def print_progress(self) -> None:
        """
        Print progress update to console.
        Format: [50/500] 10% - 45 villages/min - ✅ Village Name
        """
```

## Data Models

### Configuration

```python
@dataclass
class ScraperConfig:
    """Configuration for high-performance scraper"""
    
    # Parallelism
    num_contexts: int = 10
    tabs_per_context: int = 5
    
    # Rate limiting
    max_captcha_rpm: int = 8
    
    # Retry behavior
    max_captcha_attempts: int = 3
    max_navigation_retries: int = 2
    
    # Browser settings
    headless: bool = True
    slow_mo: int = 50  # milliseconds
    
    # Timeouts
    page_load_timeout: int = 15000  # milliseconds
    captcha_solve_timeout: int = 30000  # milliseconds
    
    # Output
    output_dir: str = "output"
    save_screenshots: bool = False
```

### VillageTask

```python
@dataclass
class VillageTask:
    """Task for processing a single village"""
    
    village_code: str
    village_name: str
    district_code: str
    taluka_code: str
    
    # Assigned worker
    worker_id: str = None
    
    # Timing
    start_time: datetime = None
    end_time: datetime = None
    
    # Status
    status: str = "pending"  # pending, processing, success, failed
    error: str = None
```

### VillageResult

```python
@dataclass
class VillageResult:
    """Result from processing a village"""
    
    # Identifiers
    village_code: str
    village_name: str
    district_code: str
    taluka_code: str
    
    # Worker info
    worker_id: str
    
    # Status
    success: bool
    error: str = None
    
    # Attempts
    captcha_attempts: int = 0
    navigation_retries: int = 0
    
    # Timing
    start_time: datetime = None
    end_time: datetime = None
    duration_seconds: float = None
    
    # Data
    raw_data: dict = None
    structured_data: dict = None
    
    # Survey info
    survey_number: str = None
```

### ScrapingSession

```python
@dataclass
class ScrapingSession:
    """Session information for a scraping job"""
    
    # Configuration
    district_code: str
    taluka_code: str
    num_contexts: int
    tabs_per_context: int
    total_workers: int
    
    # Villages
    total_villages: int
    village_codes: list[str]
    
    # Timing
    start_time: datetime
    end_time: datetime = None
    duration_seconds: float = None
    
    # Statistics
    processed: int = 0
    successful: int = 0
    failed: int = 0
    
    # Rate
    villages_per_minute: float = None
    
    # Results
    results: list[VillageResult] = field(default_factory=list)
    
    # Output
    output_dir: str = "output"
    results_file: str = None
```

## Error Handling

### Error Categories

1. **Navigation Errors**: Failed to load page, timeouts
   - Retry with exponential backoff (max 2 retries)
   - If all retries fail, mark village as failed and continue

2. **Captcha Errors**: Failed to solve captcha, invalid captcha
   - Retry with fresh captcha (max 3 attempts)
   - If all attempts fail, mark village as failed and continue

3. **Session Errors**: Lost session state, form not found
   - Attempt session recovery via navigate_back_to_form()
   - If recovery fails, perform full session reset
   - If reset fails, mark village as failed and continue

4. **Rate Limit Errors**: Captcha API quota exceeded
   - Queue request and wait for available slot
   - Log warning if wait time exceeds 30 seconds

5. **Worker Errors**: Worker crash, context closed
   - Log error with full context
   - Mark assigned villages as failed
   - Continue with remaining workers

### Error Recovery Strategy

```python
async def process_village_with_recovery(
    worker: Worker,
    village_code: str,
    max_attempts: int = 3
) -> VillageResult:
    """
    Process village with automatic error recovery.
    
    Recovery sequence:
    1. Try normal processing
    2. If captcha fails, retry with fresh captcha (up to max_attempts)
    3. If session lost, try navigate_back_to_form()
    4. If navigation fails, try full session reset
    5. If all recovery fails, mark as failed and return
    """
    
    for attempt in range(max_attempts):
        try:
            result = await worker.process_village(village_code)
            if result.success:
                return result
                
            # Captcha failed, refresh and retry
            await worker.refresh_captcha()
            
        except SessionLostError:
            # Try to recover session
            if await worker.navigate_back_to_form():
                continue
            else:
                # Full reset
                await worker.setup_session(district_code, taluka_code)
                continue
                
        except NavigationError as e:
            # Retry navigation
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                return VillageResult(
                    village_code=village_code,
                    success=False,
                    error=f"Navigation failed after {max_attempts} attempts: {e}"
                )
                
        except Exception as e:
            # Unexpected error
            return VillageResult(
                village_code=village_code,
                success=False,
                error=f"Unexpected error: {e}"
            )
    
    # All attempts exhausted
    return VillageResult(
        village_code=village_code,
        success=False,
        error=f"Failed after {max_attempts} attempts"
    )
```

## Testing Strategy

### Unit Tests

Unit tests will verify specific components and edge cases:

1. **CaptchaRateLimiter Tests**
   - Test that RPM limit is enforced
   - Test sliding window behavior
   - Test concurrent access from multiple workers

2. **VillageQueue Tests**
   - Test thread-safe get_next()
   - Test queue exhaustion
   - Test concurrent access

3. **ProgressTracker Tests**
   - Test atomic counter increments
   - Test statistics calculation
   - Test concurrent updates

4. **Worker Tests**
   - Test session setup
   - Test navigate_back_to_form()
   - Test error recovery

5. **Configuration Tests**
   - Test environment variable parsing
   - Test default values
   - Test validation

### Integration Tests

Integration tests will verify end-to-end workflows:

1. **Local Small-Scale Test**
   - Scrape 10 villages with 2 contexts × 2 tabs
   - Verify all villages processed
   - Verify results saved correctly

2. **Session Reuse Test**
   - Scrape 5 villages sequentially
   - Verify navigate_back_to_form() called between villages
   - Verify district/taluka not re-selected

3. **Rate Limiting Test**
   - Configure 2 RPM limit
   - Scrape 10 villages
   - Verify no more than 2 captcha requests per minute

4. **Error Recovery Test**
   - Inject navigation errors
   - Verify retry logic
   - Verify failed villages marked correctly

### Performance Tests

Performance tests will validate throughput targets:

1. **Local Performance Test**
   - Scrape 50 villages with 5 contexts × 5 tabs
   - Measure actual throughput
   - Verify ≥ 40 villages/minute (80% of target)

2. **GCP VM Performance Test**
   - Scrape 500 villages with 10 contexts × 5 tabs
   - Measure completion time
   - Verify ≤ 12 minutes (20% margin on 10-minute target)

3. **Scalability Test**
   - Test with 1, 2, 5, 10 contexts
   - Measure throughput vs parallelism
   - Verify linear scaling up to 10 contexts

### Testing Tools

- **pytest**: Unit and integration tests
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking for external dependencies
- **time**: Performance measurement
- **asyncio**: Concurrent test execution


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Performance Properties

**Property 1: Throughput Target**
*For any* scraping session with at least 100 villages, the measured throughput should be at least 40 villages per minute (80% of the 50 villages/minute target).
**Validates: Requirements 1.1, 1.2**

**Property 2: Completion Time Bound**
*For any* scraping session with 500 villages, the total execution time should not exceed 12 minutes (20% margin on 10-minute target).
**Validates: Requirements 1.1**

### Configuration Properties

**Property 3: Worker Pool Size**
*For any* configuration with num_contexts=N and tabs_per_context=M, the system should create exactly N×M workers.
**Validates: Requirements 1.3, 5.2, 5.3**

**Property 4: Village Limit Enforcement**
*For any* scraping session with max_villages=N, the system should process at most N villages.
**Validates: Requirements 6.2**

**Property 5: Environment Variable Configuration**
*For any* environment variable setting (NUM_CONTEXTS, TABS_PER_CONTEXT, MAX_CAPTCHA_RPM), the system should use that value in its configuration.
**Validates: Requirements 7.2**

### Data Loading Properties

**Property 6: District Data Loading**
*For any* valid district code, the system should successfully load all talukas within that district from the data file.
**Validates: Requirements 2.2**

**Property 7: Taluka Data Loading**
*For any* valid taluka code, the system should successfully load all villages within that taluka from the data file.
**Validates: Requirements 2.3**

**Property 8: Full District Processing**
*For any* district code with no taluka code specified, the system should process all talukas in that district.
**Validates: Requirements 2.4**

### Work Distribution Properties

**Property 9: Even Work Distribution**
*For any* set of N villages and M workers, the difference between the maximum and minimum villages assigned to any worker should be at most 1.
**Validates: Requirements 2.5, 5.4**

### Session Reuse Properties

**Property 10: Session State Preservation**
*For any* worker that successfully processes a village and navigates back to the form, the district and taluka dropdown values should remain unchanged.
**Validates: Requirements 1.5, 3.1, 3.2, 3.3**

**Property 11: Session Recovery Fallback**
*For any* worker where navigate_back_to_form() returns False, the system should call setup_session() to perform full re-navigation.
**Validates: Requirements 3.4, 9.3**

**Property 12: Session Restoration**
*For any* worker that performs full re-navigation via setup_session(), the district and taluka selections should be restored to their original values.
**Validates: Requirements 3.5**

### Rate Limiting Properties

**Property 13: Captcha Rate Limit Enforcement**
*For any* 60-second sliding window during execution, the number of captcha requests should not exceed max_captcha_rpm.
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Progress Tracking Properties

**Property 14: Counter Accuracy**
*For any* scraping session, the sum of successful and failed counters should equal the processed counter, and processed should be less than or equal to total.
**Validates: Requirements 8.1**

**Property 15: Atomic Counter Updates**
*For any* concurrent counter updates from multiple workers, the final counter values should be consistent (no lost updates due to race conditions).
**Validates: Requirements 8.2**

**Property 16: Progress Calculation Accuracy**
*For any* progress state, the percentage complete should equal (processed / total) × 100, and throughput should equal processed / elapsed_minutes.
**Validates: Requirements 8.3, 8.4**

**Property 17: Final Statistics Completeness**
*For any* completed scraping session, the final statistics should include total, processed, successful, failed, success_rate, and duration_seconds.
**Validates: Requirements 8.5**

### Error Handling Properties

**Property 18: Error Logging with Context**
*For any* worker error, the error log should include the village code, worker ID, and error message.
**Validates: Requirements 9.1, 7.5**

**Property 19: Graceful Error Recovery**
*For any* worker that encounters an error processing a village, the worker should mark that village as failed and continue processing the next village in its queue.
**Validates: Requirements 9.2, 9.4**

**Property 20: Failed Village Reporting**
*For any* scraping session with at least one failed village, the final report should include all failed villages with their error messages.
**Validates: Requirements 9.5**

### Result Storage Properties

**Property 21: Structured Data Extraction**
*For any* successful village scrape, the system should invoke VF7Extractor to extract structured data from the raw result.
**Validates: Requirements 10.1**

**Property 22: Complete Result File Structure**
*For any* saved result file, it should contain district_code, taluka_code, village_code, village_name, both raw_data and structured_data, and a unique timestamp-based filename.
**Validates: Requirements 10.2, 10.3, 10.5**

**Property 23: Summary Report Generation**
*For any* completed scraping session, a summary JSON file should be created containing metadata (district, taluka, total_villages, successful, duration, workers) and all village results.
**Validates: Requirements 6.5, 7.3, 7.4, 10.4**

**Property 24: Output Directory Persistence**
*For any* scraping session with output_dir=D, all result files should be saved within directory D.
**Validates: Requirements 7.3**
