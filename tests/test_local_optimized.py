"""
Local Test - Optimized Parallel Worker
Tests 10 parallel contexts on 1 taluka (~50-100 villages)

Run: python3 test_local_optimized.py
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Add cloud_run_v2 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cloud_run_v2'))

# Set environment before importing
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")
os.environ["PARALLEL_CONTEXTS"] = "5"  # Use 5 for local testing (less memory)

from parallel_worker_optimized import OptimizedDistrictScraper, JobResult


# Load Gujarat data
with open("gujarat-anyror-complete.json", "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)


async def test_single_taluka():
    """Test on single taluka (smaller scale)"""
    
    # Pick first district, first taluka
    district = GUJARAT_DATA["districts"][0]  # કચ્છ
    taluka = district["talukas"][0]  # લખપત
    
    # Create mini district with just 1 taluka
    test_district = {
        "value": district["value"],
        "label": district["label"],
        "talukas": [taluka]  # Only 1 taluka
    }
    
    # Limit villages for quick test
    max_villages = 10
    test_district["talukas"][0]["villages"] = taluka["villages"][:max_villages]
    
    print(f"\n{'='*60}")
    print("LOCAL TEST - Optimized Parallel Worker")
    print(f"{'='*60}")
    print(f"District: {district['label']}")
    print(f"Taluka: {taluka['label']}")
    print(f"Villages: {max_villages} (limited for testing)")
    print(f"Parallel contexts: {os.environ.get('PARALLEL_CONTEXTS', '5')}")
    print(f"{'='*60}\n")
    
    # Run scraper
    scraper = OptimizedDistrictScraper(parallel_contexts=5)
    
    job_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    result = await scraper.scrape_district(
        district=test_district,
        job_id=job_id,
        survey_filter=""  # No filter - list all surveys
    )
    
    # Save results
    output_file = f"test_result_{job_id}.json"
    
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            from dataclasses import asdict
            return {k: to_dict(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        return obj
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(to_dict(result), f, ensure_ascii=False, indent=2)
    
    # Generate HTML report
    generate_html_report(result, f"test_report_{job_id}.html")
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")
    print(f"Villages scraped: {result.villages_scraped}/{result.villages_total}")
    print(f"Total surveys found: {result.total_surveys}")
    print(f"Villages with surveys: {len(result.matches)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Duration: {result.duration_seconds:.1f} seconds")
    print(f"")
    print(f"📄 Results: {output_file}")
    print(f"📊 Report: test_report_{job_id}.html")
    
    return result


async def test_with_survey_filter():
    """Test searching for specific survey number"""
    
    district = GUJARAT_DATA["districts"][0]
    taluka = district["talukas"][0]
    
    test_district = {
        "value": district["value"],
        "label": district["label"],
        "talukas": [{
            **taluka,
            "villages": taluka["villages"][:20]  # 20 villages
        }]
    }
    
    print(f"\n{'='*60}")
    print("TEST - Survey Number Search")
    print(f"{'='*60}")
    print(f"Searching for survey number: 1")
    print(f"Villages to search: 20")
    print(f"{'='*60}\n")
    
    scraper = OptimizedDistrictScraper(parallel_contexts=5)
    
    result = await scraper.scrape_district(
        district=test_district,
        job_id=f"test_survey_{datetime.now().strftime('%H%M%S')}",
        survey_filter="1"  # Search for survey containing "1"
    )
    
    print(f"\n{'='*60}")
    print("SEARCH RESULTS")
    print(f"{'='*60}")
    print(f"Villages with matching surveys: {len(result.matches)}")
    
    for match in result.matches[:5]:  # Show first 5
        print(f"  • {match.village_name}: {match.surveys_found} surveys")
        for s in match.surveys[:3]:
            print(f"      - {s['text']}")
    
    return result


def generate_html_report(result: JobResult, filename: str):
    """Generate HTML report from results"""
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Report - {result.district_name}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #1a1a2e; color: #fff; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .stat {{ background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; text-align: center; }}
        .stat .num {{ font-size: 2rem; color: #00d4ff; }}
        .stat .label {{ color: #888; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        th {{ color: #888; }}
        .success {{ color: #2ecc71; }}
        .error {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Test Report: {result.district_name}</h1>
        
        <div class="stats">
            <div class="stat">
                <div class="num">{result.villages_scraped}</div>
                <div class="label">Villages Scraped</div>
            </div>
            <div class="stat">
                <div class="num">{result.total_surveys}</div>
                <div class="label">Surveys Found</div>
            </div>
            <div class="stat">
                <div class="num">{len(result.matches)}</div>
                <div class="label">Villages with Data</div>
            </div>
            <div class="stat">
                <div class="num">{result.duration_seconds:.1f}s</div>
                <div class="label">Duration</div>
            </div>
        </div>
        
        <h2>📊 Village Results</h2>
        <table>
            <tr>
                <th>Village</th>
                <th>Taluka</th>
                <th>Surveys</th>
                <th>Status</th>
            </tr>
"""
    
    for match in result.matches:
        html += f"""
            <tr>
                <td>{match.village_name}</td>
                <td>{match.taluka_name}</td>
                <td class="success">{match.surveys_found}</td>
                <td class="success">✓</td>
            </tr>
"""
    
    for err in result.errors:
        html += f"""
            <tr>
                <td>{err.get('village', 'Unknown')}</td>
                <td>-</td>
                <td>-</td>
                <td class="error">✗ {err.get('error', '')[:50]}</td>
            </tr>
"""
    
    html += """
        </table>
        
        <h2>📋 Sample Surveys</h2>
        <table>
            <tr>
                <th>Village</th>
                <th>Survey Numbers (first 5)</th>
            </tr>
"""
    
    for match in result.matches[:10]:
        surveys_str = ", ".join([s["text"] for s in match.surveys[:5]])
        if len(match.surveys) > 5:
            surveys_str += f" ... (+{len(match.surveys)-5} more)"
        html += f"""
            <tr>
                <td>{match.village_name}</td>
                <td>{surveys_str}</td>
            </tr>
"""
    
    html += """
        </table>
    </div>
</body>
</html>
"""
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)


async def main():
    """Run tests"""
    
    print("\n" + "="*60)
    print("OPTIMIZED WORKER - LOCAL TEST")
    print("="*60)
    print("\nChoose test:")
    print("  1. Quick test (10 villages, list all surveys)")
    print("  2. Survey search test (20 villages, filter by survey)")
    print("  3. Both tests")
    print("")
    
    choice = input("Enter choice (1/2/3) [default: 1]: ").strip() or "1"
    
    if choice in ["1", "3"]:
        await test_single_taluka()
    
    if choice in ["2", "3"]:
        await test_with_survey_filter()
    
    print("\n✅ Tests complete! Open the HTML report to see results.")


if __name__ == "__main__":
    asyncio.run(main())
