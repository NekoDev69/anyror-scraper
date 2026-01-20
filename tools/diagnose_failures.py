#!/usr/bin/env python3
"""
Diagnostic Test - Visual Debugging with headless=false
Run a few test searches to identify where failures occur
"""

import json
import asyncio
from swarm_scraper import SwarmScraper

# Load zone data
with open('gujarat-anyror-complete.json', 'r', encoding='utf-8') as f:
    zone_data = json.load(f)

def run_diagnostic_test():
    """Run diagnostic test on a few villages with visual browser"""
    
    # Select first district
    district = zone_data['districts'][0]  # કચ્છ (Kachchh)
    district_code = district['value']
    district_name = district['label']
    
    print(f"Testing District: {district_name} ({district_code})")
    print("=" * 60)
    
    # Get first taluka with a few villages
    taluka = district['talukas'][0]
    taluka_code = taluka['value']
    taluka_name = taluka['label']
    
    print(f"Taluka: {taluka_name} ({taluka_code})")
    print(f"Testing first 3 villages...")
    print("=" * 60)
    
    # Prepare test data - just 3 villages
    test_talukas = [{
        'value': taluka_code,
        'label': taluka_name,
        'villages': taluka['villages'][:3]  # Only first 3 villages
    }]
    
    for v in test_talukas[0]['villages']:
        print(f"  - {v['label']} ({v['value']})")
    
    print("\n" + "=" * 60)
    print("🔍 STARTING VISUAL TEST (headless=false)")
    print("Watch the browser to see where it fails!")
    print("=" * 60 + "\n")
    
    # Create scraper with headless=false and single worker
    scraper = SwarmScraper(num_workers=1, headless=False)
    
    try:
        result = scraper.scrape_district(
            district_code=district_code,
            district_name=district_name,
            talukas=test_talukas,
            output_dir='output'
        )
        
        print("\n" + "=" * 60)
        print("RESULTS:")
        print("=" * 60)
        print(f"Total: {result['total']}")
        print(f"Successful: {result['successful']}")
        print(f"Failed: {result['failed']}")
        print(f"Duration: {result['duration']:.2f}s")
        
        print("\n📋 Individual Results:")
        for r in result['results']:
            status = "✅" if r['success'] else "❌"
            village = r.get('village_name', 'Unknown')
            error = f" - {r.get('error', '')}" if not r['success'] else ""
            print(f"{status} {village}{error}")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test complete! Did you see where it failed?")
    print("=" * 60)

if __name__ == "__main__":
    run_diagnostic_test()
