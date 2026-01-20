#!/usr/bin/env python3
"""
Diagnostic Test 2 - Larger Sample with Multiple Talukas
Test 10 villages across different talukas to reproduce failures
"""

import json
import asyncio
from swarm_scraper import SwarmScraper

# Load zone data
with open('gujarat-anyror-complete.json', 'r', encoding='utf-8') as f:
    zone_data = json.load(f)

def run_expanded_test():
    """Run expanded test on multiple talukas with more villages"""
    
    # Try a different district - let's use the same one from your screenshot
    # Looking for district કચ્છ which had failures
    district = zone_data['districts'][0]  # કચ્છ (Kachchh)
    district_code = district['value']
    district_name = district['label']
    
    print(f"Testing District: {district_name} ({district_code})")
    print("=" * 60)
    
    # Get multiple talukas with several villages each
    test_talukas = []
    total_villages = 0
    
    for i, taluka in enumerate(district['talukas'][:3]):  # First 3 talukas
        villages_to_test = taluka['villages'][:5]  # 5 villages per taluka
        test_talukas.append({
            'value': taluka['value'],
            'label': taluka['label'],
            'villages': villages_to_test
        })
        total_villages += len(villages_to_test)
        
        print(f"\nTaluka #{i+1}: {taluka['label']} ({taluka['value']})")
        for v in villages_to_test:
            print(f"  - {v['label']} ({v['value']})")
    
    print("\n" + "=" * 60)
    print(f"🔍 TESTING {total_villages} VILLAGES (headless=false)")
    print("Watch for any failures in the browser!")
    print("=" * 60 + "\n")
    
    # Create scraper with 2 workers to speed it up but still visible
    scraper = SwarmScraper(num_workers=2, headless=False)
    
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
        print(f"Success Rate: {(result['successful']/result['total']*100):.1f}%")
        print(f"Duration: {result['duration']:.2f}s")
        
        print("\n📋 Individual Results:")
        successes = []
        failures = []
        
        for r in result['results']:
            if r['success']:
                successes.append(r)
            else:
                failures.append(r)
        
        if successes:
            print(f"\n✅ SUCCESSFUL ({len(successes)}):")
            for r in successes:
                print(f"   ✓ {r.get('village_name', 'Unknown')}")
        
        if failures:
            print(f"\n❌ FAILED ({len(failures)}):")
            for r in failures:
                village = r.get('village_name', 'Unknown')
                error = r.get('error', 'Unknown error')
                print(f"   ✗ {village}")
                print(f"     Error: {error}")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    run_expanded_test()
