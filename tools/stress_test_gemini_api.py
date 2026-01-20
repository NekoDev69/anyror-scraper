"""
Gemini API Stress Test - Direct API Testing
Tests concurrent request handling for Gemini captcha analysis
"""

import asyncio
import time
import base64
import statistics
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import json
from google import genai


# Load API keys
GEMINI_API_KEYS = [
    "AIzaSyDPhcBJGoFuhO-N8hrkj2XuVcYGkhNAkNA",
    "AIzaSyBS2H7Yc6ufyUC7QvjTGKtcmO_oCIxdM2Q",
    "AIzaSyDpwPZC7DHMl-RYCLEyWfXvTJ3y3ZV3thYA",
    "AIzaSyDBkyScEIGGUm2N1JwFrW32CCoAOWTbhXw",
    "AIzaSyAofd9HRMu3Zk1OYk6y0IZL_Izi5LkPkes",
    "AIzaSyDJr3HKqWOEA7vdyVgGbd1Am2xionkYbFMu",
    "AIzaSyB4nZxV7Yc8hKtFm1OqD2pLj3kR9s6TwXY",
    "AIzaSyC5oOaY8D9iLtGn2PrE3qMk4lS0t7U8VwZ",
    "AIzaSyD6pPbZ9E0jMuHo3QsF4rNl5tU1v8W9XyA",
    "AIzaSyE7qQcA0F1kNvIp4RtG6vP7wY3z0A1cDd",
    "AIzaSyF8rRdC1G2lOwJs5SuT7wQ8xZ4a1B2eEfF",
    "AIzaSyG9sSeD2H3mPxK6TvU8wQ9xZ5a2C3fGgG",
]


@dataclass
class TestResult:
    """Result of a single API call"""
    request_id: int
    success: bool
    response_time: float
    api_key_index: int
    error: str = ""
    captcha_text: str = ""
    timestamp: float = 0
    status_code: str = ""


class GeminiAPIStressTester:
    """Stress test Gemini API directly"""
    
    def __init__(self, test_image_path: str = "captcha_debug.png"):
        self.test_image_path = test_image_path
        self.test_image_base64 = None
        self.results: List[TestResult] = []
        
    def load_test_image(self) -> bool:
        """Load and encode test captcha image"""
        try:
            with open(self.test_image_path, "rb") as f:
                image_bytes = f.read()
            self.test_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            print(f"✓ Loaded test image: {self.test_image_path} ({len(image_bytes)} bytes)")
            return True
        except Exception as e:
            print(f"✗ Failed to load test image: {e}")
            return False
    
    def single_gemini_request(self, request_id: int, api_key_index: int) -> TestResult:
        """Execute a single Gemini API request"""
        start_time = time.time()
        api_key = GEMINI_API_KEYS[api_key_index % len(GEMINI_API_KEYS)]
        
        try:
            client = genai.Client(api_key=api_key)
            
            prompt = """Analyze this captcha image and extract ONLY the text/numbers shown.
Rules:
- Return ONLY the captcha text, nothing else
- No explanations, no formatting
- If you see numbers, return numbers
- If you see letters, return letters
- Remove any spaces or special characters
- Return empty string if unclear"""

            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents={
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": self.test_image_base64
                            }
                        }
                    ]
                }
            )
            
            response_time = time.time() - start_time
            
            captcha_text = ""
            if response and response.text:
                captcha_text = response.text.strip()
            
            return TestResult(
                request_id=request_id,
                success=True,
                response_time=response_time,
                api_key_index=api_key_index,
                captcha_text=captcha_text,
                timestamp=start_time,
                status_code="200"
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            
            # Extract status code if available
            status_code = "unknown"
            if "429" in error_msg or "quota" in error_msg.lower():
                status_code = "429_RATE_LIMIT"
            elif "403" in error_msg:
                status_code = "403_FORBIDDEN"
            elif "401" in error_msg:
                status_code = "401_UNAUTHORIZED"
            elif "500" in error_msg or "503" in error_msg:
                status_code = "5XX_SERVER_ERROR"
            
            return TestResult(
                request_id=request_id,
                success=False,
                response_time=response_time,
                api_key_index=api_key_index,
                error=error_msg[:200],
                timestamp=start_time,
                status_code=status_code
            )
    
    def test_sequential(self, num_requests: int = 10) -> Dict:
        """Test sequential requests (baseline)"""
        print(f"\n{'='*70}")
        print(f"SEQUENTIAL TEST: {num_requests} requests")
        print(f"{'='*70}")
        
        results = []
        start_time = time.time()
        
        for i in range(num_requests):
            api_key_index = i % len(GEMINI_API_KEYS)
            print(f"Request {i+1}/{num_requests} [Key {api_key_index}]...", end=" ", flush=True)
            result = self.single_gemini_request(i, api_key_index)
            results.append(result)
            
            status = "✓" if result.success else f"✗ {result.status_code}"
            print(f"{status} ({result.response_time:.2f}s)")
        
        total_time = time.time() - start_time
        return self._analyze_results(results, total_time, "Sequential")
    
    def test_concurrent_threads(self, num_requests: int = 50, max_workers: int = 10) -> Dict:
        """Test concurrent requests using threads"""
        print(f"\n{'='*70}")
        print(f"CONCURRENT TEST: {num_requests} requests, {max_workers} workers")
        print(f"{'='*70}")
        
        results = []
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(num_requests):
                api_key_index = i % len(GEMINI_API_KEYS)
                future = executor.submit(self.single_gemini_request, i, api_key_index)
                futures.append(future)
            
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1
                
                status = "✓" if result.success else f"✗ {result.status_code}"
                print(f"[{completed}/{num_requests}] Req {result.request_id} [Key {result.api_key_index}]: {status} ({result.response_time:.2f}s)")
        
        total_time = time.time() - start_time
        return self._analyze_results(results, total_time, f"Concurrent-{max_workers}workers")
    
    def test_burst(self, burst_size: int = 20, num_bursts: int = 3, delay_between: float = 5.0) -> Dict:
        """Test burst patterns"""
        print(f"\n{'='*70}")
        print(f"BURST TEST: {num_bursts} bursts of {burst_size} requests, {delay_between}s delay")
        print(f"{'='*70}")
        
        all_results = []
        start_time = time.time()
        
        for burst_num in range(num_bursts):
            print(f"\n--- Burst {burst_num + 1}/{num_bursts} ---")
            
            with ThreadPoolExecutor(max_workers=burst_size) as executor:
                futures = []
                for i in range(burst_size):
                    request_id = burst_num * burst_size + i
                    api_key_index = request_id % len(GEMINI_API_KEYS)
                    future = executor.submit(self.single_gemini_request, request_id, api_key_index)
                    futures.append(future)
                
                for future in as_completed(futures):
                    result = future.result()
                    all_results.append(result)
                    status = "✓" if result.success else f"✗ {result.status_code}"
                    print(f"  Req {result.request_id} [Key {result.api_key_index}]: {status} ({result.response_time:.2f}s)")
            
            if burst_num < num_bursts - 1:
                print(f"  Waiting {delay_between}s before next burst...")
                time.sleep(delay_between)
        
        total_time = time.time() - start_time
        return self._analyze_results(all_results, total_time, f"Burst-{burst_size}x{num_bursts}")
    
    def test_max_concurrent(self, max_workers: int = 50, duration_seconds: int = 30) -> Dict:
        """Test maximum concurrent load for a duration"""
        print(f"\n{'='*70}")
        print(f"MAX LOAD TEST: {max_workers} workers for {duration_seconds}s")
        print(f"{'='*70}")
        
        results = []
        start_time = time.time()
        request_counter = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            while time.time() - start_time < duration_seconds:
                # Keep submitting new requests
                api_key_index = request_counter % len(GEMINI_API_KEYS)
                future = executor.submit(self.single_gemini_request, request_counter, api_key_index)
                futures.append(future)
                request_counter += 1
                
                # Collect completed futures
                done_futures = [f for f in futures if f.done()]
                for future in done_futures:
                    result = future.result()
                    results.append(result)
                    status = "✓" if result.success else f"✗ {result.status_code}"
                    print(f"[{len(results)}] Req {result.request_id}: {status} ({result.response_time:.2f}s)")
                    futures.remove(future)
                
                time.sleep(0.1)  # Small delay to prevent overwhelming
            
            # Wait for remaining futures
            print("\nWaiting for remaining requests...")
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        total_time = time.time() - start_time
        return self._analyze_results(results, total_time, f"MaxLoad-{max_workers}workers")
    
    def _analyze_results(self, results: List[TestResult], total_time: float, test_name: str) -> Dict:
        """Analyze test results"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        response_times = [r.response_time for r in results]
        successful_times = [r.response_time for r in successful]
        
        # Analyze by API key
        key_stats = {}
        for i in range(len(GEMINI_API_KEYS)):
            key_results = [r for r in results if r.api_key_index == i]
            if key_results:
                key_successful = [r for r in key_results if r.success]
                key_stats[f"key_{i}"] = {
                    "total": len(key_results),
                    "successful": len(key_successful),
                    "success_rate": len(key_successful) / len(key_results) * 100
                }
        
        analysis = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "total_requests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) * 100 if results else 0,
            "total_time": total_time,
            "requests_per_second": len(results) / total_time if total_time > 0 else 0,
            "response_times": {
                "min": min(response_times) if response_times else 0,
                "max": max(response_times) if response_times else 0,
                "mean": statistics.mean(response_times) if response_times else 0,
                "median": statistics.median(response_times) if response_times else 0,
                "stdev": statistics.stdev(response_times) if len(response_times) > 1 else 0,
                "p95": sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0,
                "p99": sorted(response_times)[int(len(response_times) * 0.99)] if response_times else 0,
            },
            "successful_response_times": {
                "min": min(successful_times) if successful_times else 0,
                "max": max(successful_times) if successful_times else 0,
                "mean": statistics.mean(successful_times) if successful_times else 0,
                "median": statistics.median(successful_times) if successful_times else 0,
            } if successful_times else None,
            "errors": {},
            "status_codes": {},
            "key_stats": key_stats
        }
        
        # Count error types and status codes
        for result in failed:
            error_key = result.error[:80] if result.error else "Unknown"
            analysis["errors"][error_key] = analysis["errors"].get(error_key, 0) + 1
            analysis["status_codes"][result.status_code] = analysis["status_codes"].get(result.status_code, 0) + 1
        
        self._print_analysis(analysis)
        return analysis
    
    def _print_analysis(self, analysis: Dict):
        """Print formatted analysis"""
        print(f"\n{'='*70}")
        print(f"RESULTS: {analysis['test_name']}")
        print(f"{'='*70}")
        print(f"Total Requests:     {analysis['total_requests']}")
        print(f"Successful:         {analysis['successful']} ({analysis['success_rate']:.1f}%)")
        print(f"Failed:             {analysis['failed']}")
        print(f"Total Time:         {analysis['total_time']:.2f}s")
        print(f"Throughput:         {analysis['requests_per_second']:.2f} req/s")
        
        print(f"\nResponse Times (all):")
        rt = analysis['response_times']
        print(f"  Min:     {rt['min']:.3f}s")
        print(f"  Median:  {rt['median']:.3f}s")
        print(f"  Mean:    {rt['mean']:.3f}s")
        print(f"  P95:     {rt['p95']:.3f}s")
        print(f"  P99:     {rt['p99']:.3f}s")
        print(f"  Max:     {rt['max']:.3f}s")
        print(f"  StdDev:  {rt['stdev']:.3f}s")
        
        if analysis['successful_response_times']:
            print(f"\nResponse Times (successful only):")
            srt = analysis['successful_response_times']
            print(f"  Min:     {srt['min']:.3f}s")
            print(f"  Median:  {srt['median']:.3f}s")
            print(f"  Mean:    {srt['mean']:.3f}s")
            print(f"  Max:     {srt['max']:.3f}s")
        
        if analysis['status_codes']:
            print(f"\nStatus Codes:")
            for code, count in sorted(analysis['status_codes'].items()):
                print(f"  {code}: {count}")
        
        if analysis['errors']:
            print(f"\nTop Errors:")
            sorted_errors = sorted(analysis['errors'].items(), key=lambda x: x[1], reverse=True)
            for error, count in sorted_errors[:5]:
                print(f"  [{count}x] {error}")
        
        print(f"\nAPI Key Performance:")
        for key_name, stats in sorted(analysis['key_stats'].items()):
            print(f"  {key_name}: {stats['successful']}/{stats['total']} ({stats['success_rate']:.1f}%)")
    
    def run_comprehensive_test(self) -> Dict:
        """Run comprehensive stress test suite"""
        print(f"\n{'#'*70}")
        print(f"# GEMINI API STRESS TEST")
        print(f"# Available API Keys: {len(GEMINI_API_KEYS)}")
        print(f"# Test Image: {self.test_image_path}")
        print(f"# Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*70}")
        
        if not self.load_test_image():
            return {"error": "Failed to load test image"}
        
        all_results = {}
        
        # Test 1: Sequential baseline
        all_results['sequential'] = self.test_sequential(num_requests=12)
        
        # Test 2: Low concurrency
        all_results['concurrent_low'] = self.test_concurrent_threads(
            num_requests=24, 
            max_workers=6
        )
        
        # Test 3: Medium concurrency
        all_results['concurrent_medium'] = self.test_concurrent_threads(
            num_requests=60, 
            max_workers=12
        )
        
        # Test 4: High concurrency
        all_results['concurrent_high'] = self.test_concurrent_threads(
            num_requests=120, 
            max_workers=24
        )
        
        # Test 5: Burst pattern
        all_results['burst'] = self.test_burst(
            burst_size=20, 
            num_bursts=3, 
            delay_between=10.0
        )
        
        # Test 6: Maximum load
        all_results['max_load'] = self.test_max_concurrent(
            max_workers=30,
            duration_seconds=30
        )
        
        # Save results
        self._save_results(all_results)
        
        # Print final summary
        self._print_final_summary(all_results)
        
        return all_results
    
    def _save_results(self, results: Dict):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"gemini_stress_test_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✓ Results saved to: {filename}")
    
    def _print_final_summary(self, all_results: Dict):
        """Print final summary"""
        print(f"\n{'#'*70}")
        print(f"# FINAL SUMMARY")
        print(f"{'#'*70}\n")
        
        print(f"{'Test':<25} {'Reqs':<8} {'Success%':<10} {'Avg(s)':<8} {'P95(s)':<8} {'RPS':<8}")
        print(f"{'-'*70}")
        
        for test_name, result in all_results.items():
            if 'error' in result:
                continue
            
            print(f"{result['test_name']:<25} "
                  f"{result['total_requests']:<8} "
                  f"{result['success_rate']:<10.1f} "
                  f"{result['response_times']['mean']:<8.2f} "
                  f"{result['response_times']['p95']:<8.2f} "
                  f"{result['requests_per_second']:<8.2f}")
        
        print(f"\n{'#'*70}")
        print(f"# RECOMMENDATIONS")
        print(f"{'#'*70}")
        
        # Provide recommendations
        high_test = all_results.get('concurrent_high', {})
        max_test = all_results.get('max_load', {})
        
        if high_test.get('success_rate', 0) >= 95:
            print(f"✓ Excellent: API handles 24+ concurrent workers reliably")
            print(f"  Recommended: 20-30 workers for production")
        elif high_test.get('success_rate', 0) >= 85:
            print(f"⚠ Good: API handles high concurrency with minor issues")
            print(f"  Recommended: 12-20 workers for production")
        elif high_test.get('success_rate', 0) >= 70:
            print(f"⚠ Fair: API struggles with high concurrency")
            print(f"  Recommended: 6-12 workers for production")
        else:
            print(f"✗ Poor: API has significant issues with concurrency")
            print(f"  Recommended: 3-6 workers maximum")
        
        if max_test:
            print(f"\nMax Load Test:")
            print(f"  Total requests: {max_test.get('total_requests', 0)}")
            print(f"  Success rate: {max_test.get('success_rate', 0):.1f}%")
            print(f"  Throughput: {max_test.get('requests_per_second', 0):.2f} req/s")


def main():
    """Run the stress test"""
    tester = GeminiAPIStressTester()
    results = tester.run_comprehensive_test()
    
    print(f"\n✓ Gemini API stress test complete!")


if __name__ == "__main__":
    main()
