import sys
import os

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from tools.district_scraper import DistrictScraper

def main():
    print("Testing District-wide Survey Number Search (Headless=False)")
    
    # Use Kachchh district (01)
    # Zone file is in data folder but district_scraper defaults to frontend/
    zone_file = "data/gujarat-anyror-complete.json"
    
    scraper = DistrictScraper(zone_file=zone_file)
    
    # Run scrape for Kachchh (01)
    # Limit to 2 villages per taluka for quick testing
    # First taluka only (test_mode=True)
    scraper.scrape_district(
        district_name="01",
        mode="sequential",
        max_villages_per_taluka=2,
        test_mode=True,
        output_dir="output/test_district_survey",
        headless=False
    )

if __name__ == "__main__":
    main()
