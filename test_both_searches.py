#!/usr/bin/env python3
"""
Comprehensive test for AnyROR Scraper - Tests BOTH:
1. Survey Number Search (VF-7 records)
2. Owner Name Search (Know Khata by Owner Name)

Usage: python test_both_searches.py
"""

import json
import os
import sys
from datetime import datetime

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from anyror_scraper import AnyRORScraper


def test_survey_search(scraper):
    """Test Survey Number Search (VF-7)"""
    print("\n" + "=" * 60)
    print("TEST 1: SURVEY NUMBER SEARCH (VF-7)")
    print("=" * 60)

    # Use known working location from Gujarat (from gujarat-anyror-complete.json)
    # District: 01 (Kutch), Taluka: 01 (Lakhpat), Village: 040 (Akri)
    test_params = {
        "district": "01",  # Kutch
        "taluka": "01",    # Lakhpat
        "village": "040",  # Akri
        "survey": "1"      # Survey number 1
    }
    
    print(f"\n[TEST] Searching for:")
    print(f"       District: {test_params['district']}")
    print(f"       Taluka:   {test_params['taluka']}")
    print(f"       Village:  {test_params['village']}")
    print(f"       Survey:   {test_params['survey']}")
    
    try:
        result = scraper.scrape(
            target_district=test_params["district"],
            target_taluka=test_params["taluka"],
            target_village=test_params["village"],
            target_survey=test_params["survey"],
            max_captcha_attempts=5
        )
        
        success = result.get("raw", {}).get("data", {}).get("success", False)
        
        if success:
            structured = result.get("structured", {})
            owners = structured.get("owners", [])
            encumbrances = structured.get("rights_and_remarks", {}).get("entry_details", [])
            
            print(f"\n✅ SURVEY SEARCH SUCCESS!")
            print(f"   Village: {structured.get('location', {}).get('village', {}).get('name_local', 'N/A')}")
            print(f"   Khata:   {structured.get('property_identity', {}).get('khata_number', 'N/A')}")
            print(f"   Survey:  {structured.get('property_identity', {}).get('survey_number', 'N/A')}")
            print(f"   Area:    {structured.get('land_details', {}).get('total_area_raw', 'N/A')}")
            print(f"   Owners:  {len(owners)}")
            print(f"   Encumbrances: {len(encumbrances)}")
            
            if owners:
                print("\n   Owner Details:")
                for i, owner in enumerate(owners[:3], 1):
                    print(f"     {i}. {owner.get('owner_name', 'N/A')}")
            
            # Verify files were saved
            files = result.get("files", {})
            print(f"\n   Files saved:")
            print(f"     Raw:        {files.get('raw', 'N/A')}")
            print(f"     Structured: {files.get('structured', 'N/A')}")
            
            return True, result
        else:
            print(f"\n❌ SURVEY SEARCH FAILED")
            print(f"   Error: {result.get('raw', {}).get('data', {}).get('error', 'Unknown')}")
            return False, result
            
    except Exception as e:
        print(f"\n❌ SURVEY SEARCH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_owner_search(scraper):
    """Test Owner Name Search"""
    print("\n" + "=" * 60)
    print("TEST 2: OWNER NAME SEARCH (Know Khata by Owner Name)")
    print("=" * 60)

    # Use known working location that found results
    # District: 07 (Ahmedabad), Taluka: 01 (Mandal), Village: 007 (Anandpura)
    test_params = {
        "district": "07",    # Ahmedabad
        "taluka": "01",      # Mandal
        "village": "007",    # Anandpura
        "owner_name": "kumar"  # Search for kumar
    }
    
    print(f"\n[TEST] Searching for owner:")
    print(f"       District:   {test_params['district']}")
    print(f"       Taluka:     {test_params['taluka']}")
    print(f"       Village:    {test_params['village']}")
    print(f"       Owner Name: {test_params['owner_name']}")
    
    try:
        result = scraper.scrape_by_owner(
            district_code=test_params["district"],
            taluka_code=test_params["taluka"],
            village_code=test_params["village"],
            owner_name=test_params["owner_name"],
            max_captcha_attempts=5
        )
        
        if result.get("success"):
            matches = result.get("results", [])
            print(f"\n✅ OWNER SEARCH SUCCESS!")
            print(f"   District: {result.get('district', {}).get('text', 'N/A')}")
            print(f"   Taluka:   {result.get('taluka', {}).get('text', 'N/A')}")
            print(f"   Village:  {result.get('village', {}).get('text', 'N/A')}")
            print(f"   Matches:  {len(matches)}")
            
            if matches:
                print("\n   Results (first 5):")
                for i, m in enumerate(matches[:5], 1):
                    print(f"     {i}. Khata: {m.get('khata_no')} | Survey: {m.get('survey_no')} | Owner: {m.get('owner_name', '')[:40]}")
            else:
                print(f"   Message: {result.get('message', 'No matches in this village')}")
            
            # Save results
            out_file = f"output/owner_search_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.makedirs("output", exist_ok=True)
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n   Results saved: {out_file}")
            
            return True, result
        else:
            print(f"\n❌ OWNER SEARCH FAILED")
            print(f"   Error: {result.get('error', 'Unknown')}")
            return False, result
            
    except Exception as e:
        print(f"\n❌ OWNER SEARCH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    print("=" * 60)
    print("ANYROR SCRAPER - COMPREHENSIVE TEST")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    scraper = AnyRORScraper(headless=False)  # Set to False to see browser
    
    results = {"survey": None, "owner": None}
    
    try:
        scraper.start()
        
        # Test 1: Survey Search
        survey_ok, survey_result = test_survey_search(scraper)
        results["survey"] = {"success": survey_ok, "result": survey_result}
        
        # Test 2: Owner Search
        owner_ok, owner_result = test_owner_search(scraper)
        results["owner"] = {"success": owner_ok, "result": owner_result}
        
        # Summary
        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print(f"   Survey Search: {'✅ PASS' if survey_ok else '❌ FAIL'}")
        print(f"   Owner Search:  {'✅ PASS' if owner_ok else '❌ FAIL'}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[FATAL ERROR]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()
        print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

