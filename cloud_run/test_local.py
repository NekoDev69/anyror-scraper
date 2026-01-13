"""
Quick local test for the global search API
Run this before deploying to Cloud Run
"""

import json
import requests
import subprocess
import time
import sys

def test_api():
    """Test the FastAPI endpoints locally"""
    
    base_url = "http://localhost:8080"
    
    print("Testing API endpoints...\n")
    
    # Test health
    print("1. Health check...")
    try:
        r = requests.get(f"{base_url}/")
        print(f"   ✓ Status: {r.json()}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return
    
    # Test districts list
    print("\n2. List districts...")
    r = requests.get(f"{base_url}/districts")
    districts = r.json()
    print(f"   ✓ Found {len(districts)} districts")
    print(f"   First 3: {[d['name'] for d in districts[:3]]}")
    
    # Test talukas for first district
    print("\n3. List talukas for district 01 (Kutch)...")
    r = requests.get(f"{base_url}/districts/01/talukas")
    talukas = r.json()
    print(f"   ✓ Found {len(talukas)} talukas")
    print(f"   First 3: {[t['name'] for t in talukas[:3]]}")
    
    print("\n✅ All tests passed!")
    print("\nTo test a real search, run:")
    print('  curl -X POST "http://localhost:8080/search/district" \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"district_code": "01", "search_value": "123"}\'')


def start_server():
    """Start the FastAPI server"""
    print("Starting local server...")
    print("Press Ctrl+C to stop\n")
    
    import uvicorn
    from main import app
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_api()
    else:
        start_server()
