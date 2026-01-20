"""
Gemini Captcha API Stress Test
Tests concurrent request handling, rate limits, and reliability
"""

import asyncio
import time
import base64
import statistics
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

# Import the captcha solver
from captcha_solver import CaptchaSolver, GEMINI_API_KEYS


@dataclass
class TestResult:
    """Result of a single captcha solve attempt"""
    request_id: int
    success: bool
    response_time: float
    error: str = ""
    captcha_text: str = ""
    timestamp: float = 0


class CaptchaStressTester:
    """Stress test the Gemini captcha API"""
    
    def __init__(self, test_image_path: str = "captcha_debug.png"):
        self.test_image_path = test_image_path
        self.test_image_bytes = None
        self.results: List[TestResult] = []
        
    def load_test_image(self) -> bool:
        """Load test captcha image"""
        try:
            with open(self.test_image_path, "rb") as f:
                self.test_image_bytes = f.read()
            print(f"✓ Loaded test image: {self.test_image_path} ({len(self.test_image_bytes)} bytes)")
            return True
        except Exception as e:
            print(f"✗ Failed to load test image: {e}")
            return False
    
    def single_request(self, request_id: int, solver: CaptchaSolver) -> TestResult:
        """Execute a single captcha solve request"""
        start_time = time.time()
        
        try:
            captcha_text = solver.solve(self.test_image_bytes, timeout=15)
            response_time = time.time() - start_time
            
            success = bool(captcha_text)
            
            return TestResult(
                request_id=request_id,
                success=success,
                response_time=response_time,
                captcha_text=captcha_text,
                timestamp=start_time
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return TestResult(
                request_id=request_id,
                success=False,
                response_time=response_time,
                error=str(e),
                timestamp=start_time
            )
    
    def test_sequential(self, num_requests: int = 10) -> Dict:
        """Test sequential requests (baseline)"""
        print(f"\n{'='*60}")
        print(f"SEQUENTIAL TEST: {num_requests} requests")
        print(f"{'='*60}")
        
        solver = CaptchaSolver()
        results = []
        
        start_time = time.time()
        
        for i in range(num_requests):
            print(f"Request {i+1}/{num_requests}...", end=" ", flush=True)
            result = self.single_request(i, solver)
            results.append(result)
            
            status = "✓" if result.success else "✗"
            print(f"{status} ({result.response_time:.2f}s)")
        
        total_time = time.time() - start_time
        
        return self._analyze_results(results, total_time, "Sequential")
    
    def test_concurrent_threads(self, num_requests: int = 50, max_workers: int = 10) -> Dict:
        """Test concurrent requests using threads"""
        print(f"\n{'='*60}")
        print(f"CONCURRENT TEST (Threads): {num_requests} requests, {max_workers} workers")
        print(f"{'='*60}")
        
        results = []
        start_time = time.time()
        
        # Create a solver for each worker
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = []
            for i in range(num_requests):
                solver = CaptchaSolver()  # Each thread gets its own solver
                future = executor.submit(self.single_request, i, solver)
                futures.append(future)
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1
                
                status = "✓" if result.success else "✗"
                print(f"[{completed}/{num_requests}] Request {result.request_id}: {status} ({result.response_time:.2f}s)")
        
        total_time = time.time() - start_time
        
        return self._analyze_results(results, total_time, f"Concurrent-{max_workers}workers")
    
    def test_burst(self, burst_size: int = 20, num_bursts: int = 3, delay_between: float = 5.0) -> Dict:
        """Test burst patterns (simulate real-world spikes)"""
        print(f"\n{'='*60}")
        print(f"BURST TEST: {num_bursts} bursts of {burst_size} requests, {delay_between}s delay")
        print(f"{'='*60}")
        
        all_results = []
        start_time = time.time()
        
        for burst_num in range(num_bursts):
            print(f"\n--- Burst {burst_num + 1}/{num_bursts} ---")
            
            with ThreadPoolExecutor(max_workers=burst_size) as executor:
                futures = []
                for i in range(burst_size):
                    solver = CaptchaSolver()
                    request_id = burst_num * burst_size + i
                    future = executor.submit(self.single_request, request_id, solver)
                    futures.append(future)
                
                for future in as_completed(futures):
                    result = future.result()
                    all_results.append(result)
                    status = "✓" if result.success else "✗"
                    print(f"  Request {result.request_id}: {status} ({result.response_time:.2f}s)")
            
            if burst_num < num_bursts - 1:
                print(f"  Waiting {delay_between}s before next burst...")
                time.sleep(delay_between)
        
        total_time = time.time() - start_time
        
        return self._analyze_results(all_results, total_time, f"Burst-{burst_size}x{num_bursts}")
    
    def _analyze_results(self, results: List[TestResult], total_time: float, test_name: str) -> Dict:
        """Analyze test results and generate report"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        response_times = [r.response_time for r in results]
        successful_times = [r.response_time for r in successful]
        
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
            },
            "successful_response_times": {
                "min": min(successful_times) if successful_times else 0,
                "max": max(successful_times) if successful_times else 0,
                "mean": statistics.mean(successful_times) if successful_times else 0,
                "median": statistics.median(successful_times) if successful_times else 0,
            } if successful_times else None,
            "errors": {}
        }
        
        # Count error types
        for result in failed:
            error_key = result.error[:50] if result.error else "Unknown"
            analysis["errors"][error_key] = analysis["errors"].get(error_key, 0) + 1
        
        # Print summary
        self._print_analysis(analysis)
        
        return analysis
    
    def _print_analysis(self, analysis: Dict):
        """Print formatted analysis"""
        print(f"\n{'='*60}")
        print(f"RESULTS: {analysis['test_name']}")
        print(f"{'='*60}")
        print(f"Total Requests:     {analysis['total_requests']}")
        print(f"Successful:         {analysis['successful']} ({analysis['success_rate']:.1f}%)")
        print(f"Failed:             {analysis['failed']}")
        print(f"Total Time:         {analysis['total_time']:.2f}s")
        print(f"Throughput:         {analysis['requests_per_second']:.2f} req/s")
        
        print(f"\nResponse Times (all requests):")
        rt = analysis['response_times']
        print(f"  Min:     {rt['min']:.3f}s")
        print(f"  Max:     {rt['max']:.3f}s")
        print(f"  Mean:    {rt['mean']:.3f}s")
        print(f"  Median:  {rt['median']:.3f}s")
        print(f"  StdDev:  {rt['stdev']:.3f}s")
        
        if analysis['successful_response_times']:
            print(f"\nResponse Times (successful only):")
            srt = analysis['successful_response_times']
            print(f"  Min:     {srt['min']:.3f}s")
            print(f"  Max:     {srt['max']:.3f}s")
            print(f"  Mean:    {srt['mean']:.3f}s")
            print(f"  Median:  {srt['median']:.3f}s")
        
        if analysis['errors']:
            print(f"\nErrors:")
            for error, count in analysis['errors'].items():
                print(f"  {error}: {count}")
    
    def run_comprehensive_test(self) -> Dict:
        """Run comprehensive stress test suite"""
        print(f"\n{'#'*60}")
        print(f"# GEMINI CAPTCHA API STRESS TEST")
        print(f"# Available API Keys: {len(GEMINI_API_KEYS)}")
        print(f"# Test Image: {self.test_image_path}")
        print(f"# Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}")
        
        if not self.load_test_image():
            return {"error": "Failed to load test image"}
        
        all_results = {}
        
        # Test 1: Sequential baseline (10 requests)
        all_results['sequential'] = self.test_sequential(num_requests=10)
        
        # Test 2: Low concurrency (20 requests, 5 workers)
        all_results['concurrent_low'] = self.test_concurrent_threads(
            num_requests=20, 
            max_workers=5
        )
        
        # Test 3: Medium concurrency (50 requests, 10 workers)
        all_results['concurrent_medium'] = self.test_concurrent_threads(
            num_requests=50, 
            max_workers=10
        )
        
        # Test 4: High concurrency (100 requests, 20 workers)
        all_results['concurrent_high'] = self.test_concurrent_threads(
            num_requests=100, 
            max_workers=20
        )
        
        # Test 5: Burst pattern
        all_results['burst'] = self.test_burst(
            burst_size=15, 
            num_bursts=3, 
            delay_between=5.0
        )
        
        # Save results
        self._save_results(all_results)
        
        # Print final summary
        self._print_final_summary(all_results)
        
        return all_results
    
    def _save_results(self, results: Dict):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"stress_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✓ Results saved to: {filename}")
    
    def _print_final_summary(self, all_results: Dict):
        """Print final summary comparing all tests"""
        print(f"\n{'#'*60}")
        print(f"# FINAL SUMMARY")
        print(f"{'#'*60}\n")
        
        print(f"{'Test Name':<25} {'Requests':<10} {'Success%':<10} {'Avg Time':<10} {'Throughput':<12}")
        print(f"{'-'*75}")
        
        for test_name, result in all_results.items():
            if 'error' in result:
                continue
            
            print(f"{result['test_name']:<25} "
                  f"{result['total_requests']:<10} "
                  f"{result['success_rate']:<10.1f} "
                  f"{result['response_times']['mean']:<10.3f} "
                  f"{result['requests_per_second']:<12.2f}")
        
        print(f"\n{'#'*60}")
        print(f"# RECOMMENDATIONS")
        print(f"{'#'*60}")
        
        # Analyze and provide recommendations
        concurrent_high = all_results.get('concurrent_high', {})
        if concurrent_high and concurrent_high.get('success_rate', 0) >= 95:
            print(f"✓ API handles high concurrency well (20+ workers)")
            print(f"  Recommended: 15-20 concurrent workers for production")
        elif concurrent_high and concurrent_high.get('success_rate', 0) >= 80:
            print(f"⚠ API handles high concurrency with some failures")
            print(f"  Recommended: 10-15 concurrent workers for production")
        else:
            print(f"✗ API struggles with high concurrency")
            print(f"  Recommended: 5-10 concurrent workers for production")
        
        # Check response times
        if concurrent_high:
            avg_time = concurrent_high.get('response_times', {}).get('mean', 0)
            if avg_time < 2.0:
                print(f"✓ Response times are excellent (<2s average)")
            elif avg_time < 5.0:
                print(f"⚠ Response times are acceptable (2-5s average)")
            else:
                print(f"✗ Response times are slow (>5s average)")


def main():
    """Run the stress test"""
    tester = CaptchaStressTester()
    results = tester.run_comprehensive_test()
    
    print(f"\n✓ Stress test complete!")


if __name__ == "__main__":
    main()
