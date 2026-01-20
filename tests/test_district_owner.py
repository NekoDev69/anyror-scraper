import sys
import os

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from tools.global_owner_scraper import GlobalOwnerScraper

def main():
    print("Testing District-wide Owner Name Search (Headless=False)")
    
    # Target District: Kachchh (01)
    # Owner Name: Patel
    # Filter to first 2 talukas for speed: "01" (Lakhpat), "02" (Rapar)
    
    scraper = GlobalOwnerScraper(
        owner_name="Kumar",
        district_code="01",
        headless=False,
        num_workers=1,
        taluka_codes=["04"] # Anjar
    )
    
    # Override villages to only target Satapar (028)
    def get_satapar_villages(self):
        return [{
            "code": "04",
            "name": "અંજાર",
            "villages": [{"code": "028", "name": "સતાપર"}]
        }]
    
    scraper.get_district_villages = get_satapar_villages.__get__(scraper, GlobalOwnerScraper)
    
    # We need to monkeypatch the zone file path in GlobalOwnerScraper if it's hardcoded
    # Looking at global_owner_scraper.py:62: 
    # with open("frontend/gujarat-anyror-complete.json", 'r', encoding='utf-8') as f:
    
    # Let's ensure the file exists at that path or symlink it
    if not os.path.exists("frontend/gujarat-anyror-complete.json"):
        print("Warning: frontend/gujarat-anyror-complete.json not found, using data/gujarat-anyror-complete.json")
        # For the test script, we might need to be in the root dir
    
    scraper.run()

if __name__ == "__main__":
    main()
