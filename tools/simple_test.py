"""
Simple direct test to prove extraction works
"""

from anyror_scraper import AnyRORScraper


def simple_test():
    print("🧪 SIMPLE EXTRACTION TEST")
    print("=" * 40)

    scraper = AnyRORScraper(headless=False)

    try:
        scraper.start()

        # Use main scrape function
        result = scraper.scrape(
            target_district="Kutch",
            target_taluka="Lakhpat",
            target_village="Akari",
            max_captcha_attempts=3,
        )

        print("📊 RESULT ANALYSIS:")
        print("=" * 30)

        if result and result.get("raw", {}).get("data", {}).get("success"):
            data = result["raw"]["data"]
            print("✅ SUCCESSFUL EXTRACTION!")
            print(f"   Tables found: {len(data.get('tables', []))}")
            print(f"   Property details: {len(data.get('property_details', {}))}")

            # Show sample extracted data
            if data.get("tables"):
                table_text = data["tables"][0].get("text", "")[:200]
                print(f"   Sample data: {table_text}...")

            if data.get("property_details"):
                details = data["property_details"]
                print("   Extracted fields:")
                for key, value in list(details.items())[:3]:
                    if value:
                        print(f"     {key}: {str(value)[:30]}...")

            return True
        else:
            print("❌ Extraction failed")
            if result:
                error = result.get("raw", {}).get("data", {}).get("error", "unknown")
                print(f"   Error: {error}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        scraper.close()


if __name__ == "__main__":
    success = simple_test()

    if success:
        print("\n🎉 PROVEN! System extracts actual records!")
    else:
        print("\n❌ Could not extract records")
