"""
Live test with visible browser to see what's really happening
"""

from anyror_scraper import AnyRORScraper
import time


def run_live_test():
    print("🔥 LIVE TEST - VISIBLE BROWSER")
    print("=" * 50)

    scraper = AnyRORScraper(headless=False)  # Make browser visible

    try:
        scraper.start()

        print("🌐 Browser launched - navigate to site...")
        scraper.navigate()

        print("⏳ Wait 10 seconds to see what loads...")
        time.sleep(10)

        print("📋 Try to select VF-7...")
        scraper.select_vf7()

        print("⏳ Wait 5 seconds...")
        time.sleep(5)

        print("🏛️ Get district options...")
        districts = scraper.get_options(scraper.SELECTORS["district"])
        print(f"Found {len(districts)} districts:")
        for i, d in enumerate(districts[:5]):
            print(f"  {i + 1}. {d['text']} ({d['value']})")

        if districts:
            print("✅ Districts found, trying to select first...")
            scraper.select_district(districts[0]["value"])
            time.sleep(3)

            print("🏘️ Get taluka options...")
            talukas = scraper.get_options(scraper.SELECTORS["taluka"])
            print(f"Found {len(talukas)} talukas")

            if talukas:
                print("✅ Talukas found, trying to select first...")
                scraper.select_taluka(talukas[0]["value"])
                time.sleep(3)

                print("📍 Get village options...")
                villages = scraper.get_options(scraper.SELECTORS["village"])
                print(f"Found {len(villages)} villages")

                if villages:
                    print("✅ Villages found!")
                    print(
                        "⏳ Keeping browser open for 30 seconds - go check what's happening..."
                    )
                    time.sleep(30)
                else:
                    print("❌ NO VILLAGES FOUND!")
            else:
                print("❌ NO TALUKAS FOUND!")
        else:
            print("❌ NO DISTRICTS FOUND!")

        print("📸 Taking screenshot...")
        scraper.page.screenshot(path="live_test_screenshot.png", full_page=True)
        print("Screenshot saved: live_test_screenshot.png")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("⏳ Keeping browser open for 10 more seconds...")
        time.sleep(10)
        scraper.close()


if __name__ == "__main__":
    run_live_test()
