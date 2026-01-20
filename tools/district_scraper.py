#!/usr/bin/env python3
"""
District Scraper CLI - Scrape entire districts automatically
Uses gujarat-anyror-complete.json to find all talukas and villages
"""

import json
import argparse
import sys
from datetime import datetime
from anyror_scraper import AnyRORScraper

# Try to import parallel scraper if available
try:
    from anyror_scraper import ParallelAnyRORScraper
    PARALLEL_AVAILABLE = True
except ImportError:
    PARALLEL_AVAILABLE = False
    print("Note: Parallel mode not available, using sequential mode only")


class DistrictScraper:
    """Scrape entire districts using zone data"""
    
    def __init__(self, zone_file: str = "frontend/gujarat-anyror-complete.json"):
        self.zone_file = zone_file
        self.zone_data = None
        self.load_zone_data()
    
    def load_zone_data(self):
        """Load Gujarat zone data"""
        try:
            with open(self.zone_file, 'r', encoding='utf-8') as f:
                self.zone_data = json.load(f)
            print(f"✓ Loaded zone data: {self.zone_data['totalDistricts']} districts, "
                  f"{self.zone_data['totalTalukas']} talukas, "
                  f"{self.zone_data['totalVillages']} villages")
        except FileNotFoundError:
            print(f"✗ Error: Zone file not found: {self.zone_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"✗ Error: Invalid JSON in zone file: {e}")
            sys.exit(1)
    
    def list_districts(self):
        """List all available districts"""
        print("\n" + "="*60)
        print("AVAILABLE DISTRICTS")
        print("="*60)
        
        for i, district in enumerate(self.zone_data["districts"], 1):
            code = district["value"]
            name = district["label"]
            talukas = len(district["talukas"])
            villages = sum(len(t["villages"]) for t in district["talukas"])
            
            print(f"{i:2d}. {name:20s} (Code: {code}) - {talukas:3d} talukas, {villages:5d} villages")
        
        print("="*60)
    
    def find_district(self, search_term: str):
        """Find district by name or code"""
        search_lower = search_term.lower()
        
        # Try exact code match first
        for district in self.zone_data["districts"]:
            if district["value"] == search_term:
                return district
        
        # Try name match (partial)
        for district in self.zone_data["districts"]:
            if search_lower in district["label"].lower():
                return district
        
        # Try English name match (common names)
        name_map = {
            "ahmedabad": "અમદાવાદ",
            "surat": "સુરત",
            "vadodara": "વડોદરા",
            "rajkot": "રાજકોટ",
            "bhavnagar": "ભાવનગર",
            "jamnagar": "જામનગર",
            "junagadh": "જુનાગઢ",
            "kutch": "કચ્છ",
            "mehsana": "મહેસાણા",
            "gandhinagar": "ગાંધીનગર",
            "anand": "આણંદ",
            "kheda": "ખેડા",
            "patan": "પાટણ",
            "banaskantha": "બનાસકાંઠા",
            "sabarkantha": "સાબરકાંઠા",
        }
        
        if search_lower in name_map:
            gujarati_name = name_map[search_lower]
            for district in self.zone_data["districts"]:
                if gujarati_name in district["label"]:
                    return district
        
        return None
    
    def show_district_info(self, district: dict):
        """Show detailed district information"""
        print("\n" + "="*60)
        print(f"DISTRICT: {district['label']} (Code: {district['value']})")
        print("="*60)
        
        total_villages = 0
        for i, taluka in enumerate(district["talukas"], 1):
            villages = len(taluka["villages"])
            total_villages += villages
            print(f"{i:2d}. {taluka['label']:30s} (Code: {taluka['value']}) - {villages:4d} villages")
        
        print("="*60)
        print(f"TOTAL: {len(district['talukas'])} talukas, {total_villages} villages")
        print("="*60)
    
    def scrape_district(self, district_name: str, mode: str = "sequential", 
                       max_villages_per_taluka: int = None, 
                       test_mode: bool = False,
                       output_dir: str = "output",
                       headless: bool = True):
        """
        Scrape entire district
        
        Args:
            district_name: District name or code (e.g., "Ahmedabad", "અમદાવાદ", "07")
            mode: "sequential" or "parallel"
            max_villages_per_taluka: Limit villages per taluka (for testing)
            test_mode: If True, only scrape first taluka
            output_dir: Output directory
            headless: Whether to run in headless mode
        """
        # Find district
        district = self.find_district(district_name)
        if not district:
            print(f"✗ District not found: {district_name}")
            print("\nAvailable districts:")
            self.list_districts()
            return None
        
        # Show info
        self.show_district_info(district)
        
        # Confirm
        if not test_mode:
            total_villages = sum(len(t["villages"]) for t in district["talukas"])
            if max_villages_per_taluka:
                estimated = len(district["talukas"]) * max_villages_per_taluka
                print(f"\n⚠️  Will scrape approximately {estimated} villages (limited to {max_villages_per_taluka} per taluka)")
            else:
                print(f"\n⚠️  Will scrape ALL {total_villages} villages in this district!")
            
            response = input("\nContinue? (yes/no): ").strip().lower()
            if response not in ["yes", "y"]:
                print("Cancelled.")
                return None
        
        # Start scraping
        print(f"\n{'='*60}")
        print(f"STARTING {mode.upper()} SCRAPE")
        print(f"District: {district['label']}")
        print(f"Mode: {mode}")
        if test_mode:
            print("Test Mode: Only first taluka")
        if max_villages_per_taluka:
            print(f"Limit: {max_villages_per_taluka} villages per taluka")
        print(f"{'='*60}\n")
        
        start_time = datetime.now()
        
        if mode == "parallel" and PARALLEL_AVAILABLE:
            scraper = ParallelAnyRORScraper(
                num_tabs=5,
                num_contexts=10,
                headless=headless
            )
            stats = self._scrape_district_parallel(scraper, district, max_villages_per_taluka, test_mode, output_dir)
        else:
            if mode == "parallel" and not PARALLEL_AVAILABLE:
                print("⚠️  Parallel mode not available, using sequential mode")
            scraper = AnyRORScraper(headless=headless)
            try:
                scraper.start()
                stats = self._scrape_district_sequential(scraper, district, max_villages_per_taluka, test_mode, output_dir)
            finally:
                scraper.close()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Final summary
        print(f"\n{'='*60}")
        print("SCRAPE COMPLETE")
        print(f"{'='*60}")
        print(f"District: {district['label']}")
        print(f"Talukas processed: {stats['talukas_processed']}")
        print(f"Villages: {stats['villages_successful']}/{stats['villages_attempted']}")
        print(f"Success rate: {stats['success_rate']:.1f}%")
        print(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
        if stats['villages_successful'] > 0:
            print(f"Avg time per village: {duration/stats['villages_successful']:.1f}s")
        print(f"Output: {output_dir}/")
        print(f"{'='*60}")
        
        return stats
    
    def _scrape_district_sequential(self, scraper, district, max_villages_per_taluka, test_mode, output_dir):
        """Scrape district sequentially"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        stats = {
            "talukas_processed": 0,
            "villages_attempted": 0,
            "villages_successful": 0,
            "success_rate": 0.0
        }
        
        district_code = district["value"]
        talukas = district["talukas"][:1] if test_mode else district["talukas"]
        
        for i, taluka in enumerate(talukas, 1):
            taluka_code = taluka["value"]
            taluka_name = taluka["label"]
            
            print(f"\n[{i}/{len(talukas)}] TALUKA: {taluka_name} (Code: {taluka_code})")
            
            # Get village codes
            villages = taluka["villages"]
            village_codes = [v["value"] for v in villages]
            
            if max_villages_per_taluka:
                village_codes = village_codes[:max_villages_per_taluka]
            
            print(f"Processing {len(village_codes)} villages...")
            
            try:
                results = scraper.scrape_multiple_villages(
                    district_code=district_code,
                    taluka_code=taluka_code,
                    village_codes=village_codes,
                    max_captcha_attempts=3
                )
                
                # Update stats
                stats["villages_attempted"] += len(village_codes)
                stats["villages_successful"] += sum(1 for r in results if r.get("success"))
                stats["talukas_processed"] += 1
                
                # Save taluka results
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                taluka_file = os.path.join(
                    output_dir,
                    f"district_{district_code}_taluka_{taluka_code}_{timestamp}.json"
                )
                
                with open(taluka_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "district": {"code": district_code, "name": district["label"]},
                        "taluka": {"code": taluka_code, "name": taluka_name},
                        "results": results,
                        "stats": {
                            "total": len(village_codes),
                            "successful": sum(1 for r in results if r.get("success"))
                        }
                    }, f, ensure_ascii=False, indent=2)
                
                print(f"✓ Saved: {taluka_file}")
                
            except Exception as e:
                print(f"✗ Error: {e}")
                continue
        
        # Calculate success rate
        if stats["villages_attempted"] > 0:
            stats["success_rate"] = (stats["villages_successful"] / stats["villages_attempted"]) * 100
        
        return stats
    
    def _scrape_district_parallel(self, scraper, district, max_villages_per_taluka, test_mode, output_dir):
        """Scrape district in parallel"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        stats = {
            "talukas_processed": 0,
            "villages_attempted": 0,
            "villages_successful": 0,
            "success_rate": 0.0
        }
        
        district_code = district["value"]
        talukas = district["talukas"][:1] if test_mode else district["talukas"]
        
        for i, taluka in enumerate(talukas, 1):
            taluka_code = taluka["value"]
            taluka_name = taluka["label"]
            
            print(f"\n[{i}/{len(talukas)}] TALUKA: {taluka_name} (Code: {taluka_code})")
            
            # Get village codes
            villages = taluka["villages"]
            village_codes = [v["value"] for v in villages]
            
            if max_villages_per_taluka:
                village_codes = village_codes[:max_villages_per_taluka]
            
            print(f"Processing {len(village_codes)} villages in parallel...")
            
            try:
                result = scraper.scrape_villages_parallel(
                    district_code=district_code,
                    taluka_code=taluka_code,
                    village_codes=village_codes,
                    max_captcha_attempts=3
                )
                
                # Update stats
                stats["villages_attempted"] += len(village_codes)
                stats["villages_successful"] += sum(1 for r in result if r.get("success"))
                stats["talukas_processed"] += 1
                
                print(f"✓ Taluka complete: {sum(1 for r in result if r.get('success'))}/{len(village_codes)}")
                
            except Exception as e:
                print(f"✗ Error: {e}")
                continue
        
        # Calculate success rate
        if stats["villages_attempted"] > 0:
            stats["success_rate"] = (stats["villages_successful"] / stats["villages_attempted"]) * 100
        
        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Scrape entire districts from Gujarat AnyROR portal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all districts
  python district_scraper.py --list
  
  # Show district info
  python district_scraper.py --info Ahmedabad
  python district_scraper.py --info અમદાવાદ
  python district_scraper.py --info 07
  
  # Test mode (first taluka, 5 villages)
  python district_scraper.py --district Ahmedabad --test
  
  # Scrape district (sequential, limit 10 villages per taluka)
  python district_scraper.py --district Ahmedabad --limit 10
  
  # Scrape entire district (parallel mode)
  python district_scraper.py --district Ahmedabad --mode parallel
  
  # Scrape entire district (all villages, sequential)
  python district_scraper.py --district અમદાવાદ --mode sequential
        """
    )
    
    parser.add_argument("--list", action="store_true", help="List all available districts")
    parser.add_argument("--info", metavar="DISTRICT", help="Show district information")
    parser.add_argument("--district", metavar="NAME", help="District to scrape (name or code)")
    parser.add_argument("--mode", choices=["sequential", "parallel"], default="sequential",
                       help="Scraping mode (default: sequential)")
    parser.add_argument("--limit", type=int, metavar="N",
                       help="Limit villages per taluka (for testing)")
    parser.add_argument("--test", action="store_true",
                       help="Test mode: only first taluka, 5 villages")
    parser.add_argument("--output", default="output", metavar="DIR",
                       help="Output directory (default: output)")
    parser.add_argument("--zone-file", default="frontend/gujarat-anyror-complete.json",
                       help="Path to zone data JSON file")
    
    args = parser.parse_args()
    
    # Create scraper
    scraper = DistrictScraper(zone_file=args.zone_file)
    
    # Handle commands
    if args.list:
        scraper.list_districts()
    
    elif args.info:
        district = scraper.find_district(args.info)
        if district:
            scraper.show_district_info(district)
        else:
            print(f"✗ District not found: {args.info}")
            scraper.list_districts()
    
    elif args.district:
        # Test mode defaults
        if args.test:
            limit = 5
        else:
            limit = args.limit
        
        scraper.scrape_district(
            district_name=args.district,
            mode=args.mode,
            max_villages_per_taluka=limit,
            test_mode=args.test,
            output_dir=args.output
        )
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
