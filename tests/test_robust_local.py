#!/usr/bin/env python3
"""
Robust Local Test
Tests the production-grade worker on a small scale

Run: python3 test_robust_local.py
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Setup environment
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")
os.environ["PARALLEL_CONTEXTS"] = "5"  # 5 for local testing

# Add path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cloud_run_v2'))

from robust_worker import RobustDistrictScraper, JobResult, logger

# Load Gujarat data
with open("gujarat-anyror-complete.json", "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)


def create_test_district(num_villages: int = 10) -> dict:
    """Create a test district with limited villages"""
    
    district = GUJARAT_DATA["districts"][0]  # કચ્છ
    taluka = district["talukas"][0]  # લખપત
    
    return {
        "value": district["value"],
        "label": f"{district['label']} (TEST)",
        "talukas": [{
            "value": taluka["value"],
            "label": taluka["label"],
            "villages": taluka["villages"][:num_villages]
        }]
    }


def generate_report(result: JobResult, filename: str):
    """Generate detailed HTML report"""
    
    success_rate = (result.villages_success / result.villages_total * 100) if result.villages_total > 0 else 0
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Robust Test Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 30px;
        }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        
        h1 {{ 
            font-size: 2rem;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }}
        
        .stat {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        
        .stat .value {{
            font-size: 2rem;
            font-weight: 700;
            color: #00d4ff;
        }}
        
        .stat .label {{
            color: #888;
            font-size: 0.85rem;
            margin-top: 5px;
        }}
        
        .stat.success .value {{ color: #22c55e; }}
        .stat.error .value {{ color: #ef4444; }}
        .stat.warning .value {{ color: #f59e0b; }}
        
        .section {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
        }}
        
        .section h2 {{
            color: #00d4ff;
            font-size: 1.2rem;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        
        th {{
            color: #888;
            font-weight: 500;
            font-size: 0.85rem;
            text-transform: uppercase;
        }}
        
        tr:hover {{ background: rgba(255,255,255,0.02); }}
        
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
        }}
        
        .badge-success {{ background: rgba(34,197,94,0.2); color: #22c55e; }}
        .badge-error {{ background: rgba(239,68,68,0.2); color: #ef4444; }}
        .badge-warning {{ background: rgba(245,158,11,0.2); color: #f59e0b; }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }}
        
        .progress-bar .fill {{
            height: 100%;
            background: linear-gradient(90deg, #22c55e, #00d4ff);
            border-radius: 4px;
        }}
        
        .survey-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 5px;
        }}
        
        .survey-tag {{
            background: rgba(0,212,255,0.1);
            color: #00d4ff;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
        }}
        
        .error-msg {{
            color: #ef4444;
            font-size: 0.85rem;
        }}
        
        .meta {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            font-size: 0.9rem;
        }}
        
        .meta-item {{
            background: rgba(0,0,0,0.2);
            padding: 10px 15px;
            border-radius: 8px;
        }}
        
        .meta-item .key {{ color: #888; }}
        .meta-item .val {{ color: #fff; margin-top: 3px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Robust Worker Test Report</h1>
        <p class="subtitle">District: {result.district_name} | Job: {result.job_id}</p>
        
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat">
                <div class="value">{result.villages_total}</div>
                <div class="label">Total Villages</div>
            </div>
            <div class="stat success">
                <div class="value">{result.villages_success}</div>
                <div class="label">Successful</div>
            </div>
            <div class="stat error">
                <div class="value">{result.villages_failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="stat">
                <div class="value">{result.total_surveys}</div>
                <div class="label">Surveys Found</div>
            </div>
            <div class="stat">
                <div class="value">{result.duration_seconds:.1f}s</div>
                <div class="label">Duration</div>
            </div>
        </div>
        
        <!-- Progress -->
        <div class="section">
            <h2>📊 Success Rate</h2>
            <div class="progress-bar">
                <div class="fill" style="width: {success_rate}%"></div>
            </div>
            <p style="text-align: center; color: #888;">{success_rate:.1f}% success rate</p>
        </div>
        
        <!-- Successful Villages -->
        <div class="section">
            <h2>✅ Villages with Surveys ({len(result.matches)})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Village</th>
                        <th>Taluka</th>
                        <th>Surveys</th>
                        <th>Time</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for match in result.matches:
        surveys_preview = ", ".join([s["text"] for s in match.surveys[:3]])
        if len(match.surveys) > 3:
            surveys_preview += f" +{len(match.surveys)-3} more"
        
        html += f"""
                    <tr>
                        <td><strong>{match.village_name}</strong></td>
                        <td>{match.taluka_name}</td>
                        <td>
                            <span class="badge badge-success">{match.surveys_found}</span>
                            <div class="survey-list">
                                {' '.join([f'<span class="survey-tag">{s["text"]}</span>' for s in match.surveys[:5]])}
                            </div>
                        </td>
                        <td>{match.duration_ms}ms</td>
                        <td><span class="badge badge-success">Success</span></td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
        </div>
"""
    
    # Errors section
    if result.errors:
        html += f"""
        <div class="section">
            <h2>❌ Errors ({len(result.errors)})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Village</th>
                        <th>Error</th>
                    </tr>
                </thead>
                <tbody>
"""
        for err in result.errors:
            html += f"""
                    <tr>
                        <td>{err.get('village', 'Unknown')}</td>
                        <td class="error-msg">{err.get('error', 'Unknown error')}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""
    
    # Meta info
    html += f"""
        <div class="section">
            <h2>ℹ️ Job Details</h2>
            <div class="meta">
                <div class="meta-item">
                    <div class="key">Job ID</div>
                    <div class="val">{result.job_id}</div>
                </div>
                <div class="meta-item">
                    <div class="key">Started</div>
                    <div class="val">{result.started_at}</div>
                </div>
                <div class="meta-item">
                    <div class="key">Completed</div>
                    <div class="val">{result.completed_at}</div>
                </div>
                <div class="meta-item">
                    <div class="key">Survey Filter</div>
                    <div class="val">{result.survey_filter or 'None (all surveys)'}</div>
                </div>
                <div class="meta-item">
                    <div class="key">Parallel Contexts</div>
                    <div class="val">{os.environ.get('PARALLEL_CONTEXTS', '5')}</div>
                </div>
                <div class="meta-item">
                    <div class="key">Talukas</div>
                    <div class="val">{result.talukas_total}</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)


async def run_test(num_villages: int = 10, survey_filter: str = ""):
    """Run the robust test"""
    
    print("\n" + "="*60)
    print("🧪 ROBUST WORKER LOCAL TEST")
    print("="*60)
    print(f"Villages: {num_villages}")
    print(f"Parallel contexts: {os.environ.get('PARALLEL_CONTEXTS', '5')}")
    print(f"Survey filter: {survey_filter or 'None'}")
    print("="*60 + "\n")
    
    # Create test district
    test_district = create_test_district(num_villages)
    
    # Run scraper
    scraper = RobustDistrictScraper(parallel_contexts=int(os.environ.get("PARALLEL_CONTEXTS", "5")))
    
    job_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    result = await scraper.scrape_district(
        district=test_district,
        job_id=job_id,
        survey_filter=survey_filter
    )
    
    # Save JSON results
    from dataclasses import asdict
    
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_dict(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        return obj
    
    json_file = f"test_result_{job_id}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(to_dict(result), f, ensure_ascii=False, indent=2)
    
    # Generate HTML report
    html_file = f"test_report_{job_id}.html"
    generate_report(result, html_file)
    
    # Print summary
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("="*60)
    print(f"Villages: {result.villages_success}/{result.villages_total} success ({result.villages_failed} failed)")
    print(f"Surveys found: {result.total_surveys}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"")
    print(f"📄 JSON: {json_file}")
    print(f"📊 Report: {html_file}")
    print("")
    
    # Open report in browser
    try:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(html_file)}")
    except:
        pass
    
    return result


def main():
    """Main entry point"""
    
    print("\n🔧 Robust Worker Test")
    print("-" * 40)
    print("Options:")
    print("  1. Quick test (10 villages)")
    print("  2. Medium test (30 villages)")
    print("  3. Full taluka test (~100 villages)")
    print("  4. Survey search test (20 villages, filter='1')")
    print("")
    
    choice = input("Select test [1-4, default=1]: ").strip() or "1"
    
    if choice == "1":
        asyncio.run(run_test(num_villages=10))
    elif choice == "2":
        asyncio.run(run_test(num_villages=30))
    elif choice == "3":
        asyncio.run(run_test(num_villages=100))
    elif choice == "4":
        asyncio.run(run_test(num_villages=20, survey_filter="1"))
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
