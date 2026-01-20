#!/usr/bin/env python3
"""
Capture a captcha and show before/after preprocessing
"""

from anyror_scraper import AnyRORScraper
from PIL import Image
import io

print("="*70)
print("CAPTCHA PREPROCESSING - BEFORE/AFTER COMPARISON")
print("="*70)

# Initialize
print("\n1. Starting browser...")
scraper = AnyRORScraper(headless=False)
scraper.start()

# Navigate and get captcha
print("2. Navigating to form...")
scraper.page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
scraper.page.wait_for_load_state("networkidle")

print("3. Selecting VF-7...")
scraper.page.locator("#ContentPlaceHolder1_drpLandRecord").select_option("1")

import time
time.sleep(2)

print("4. Capturing captcha...")
captcha_bytes = scraper.get_captcha_image()

if not captcha_bytes:
    print("❌ Failed to capture captcha!")
    scraper.close()
    exit(1)

print(f"✓ Captured captcha ({len(captcha_bytes)} bytes)")

# Save original
with open("captcha_before.png", "wb") as f:
    f.write(captcha_bytes)
print("✓ Saved: captcha_before.png")

# Apply preprocessing
print("\n5. Applying preprocessing...")
processed_bytes = scraper.captcha_solver._preprocess_image(captcha_bytes)

with open("captcha_after.png", "wb") as f:
    f.write(processed_bytes)
print("✓ Saved: captcha_after.png")

# Show image info
print("\n6. Image comparison:")
print("-"*70)

original = Image.open(io.BytesIO(captcha_bytes))
processed = Image.open(io.BytesIO(processed_bytes))

print(f"BEFORE:")
print(f"  Size: {original.size}")
print(f"  Mode: {original.mode}")
print(f"  File size: {len(captcha_bytes)} bytes")

print(f"\nAFTER:")
print(f"  Size: {processed.size}")
print(f"  Mode: {processed.mode}")
print(f"  File size: {len(processed_bytes)} bytes")

# Test with Vision API
print("\n7. Testing with Google Vision API...")
print("-"*70)

from google.cloud import vision
from google.oauth2 import service_account

try:
    credentials = service_account.Credentials.from_service_account_file('vision-credentials.json')
    client = vision.ImageAnnotatorClient(credentials=credentials)
    
    # Test original
    print("\nOriginal image:")
    image = vision.Image(content=captcha_bytes)
    response = client.text_detection(image=image)
    if response.text_annotations:
        text = response.text_annotations[0].description.strip()
        cleaned = ''.join(c for c in text if c.isalnum())
        print(f"  Detected: '{text}'")
        print(f"  Cleaned: '{cleaned}'")
    else:
        print("  No text detected")
    
    # Test preprocessed
    print("\nPreprocessed image:")
    image = vision.Image(content=processed_bytes)
    response = client.text_detection(image=image)
    if response.text_annotations:
        text = response.text_annotations[0].description.strip()
        cleaned = ''.join(c for c in text if c.isalnum())
        print(f"  Detected: '{text}'")
        print(f"  Cleaned: '{cleaned}'")
    else:
        print("  No text detected")
        
except Exception as e:
    print(f"  Error: {e}")

# Cleanup
scraper.close()

print("\n" + "="*70)
print("COMPARISON COMPLETE!")
print("="*70)
print("\nFiles saved:")
print("  - captcha_before.png (original)")
print("  - captcha_after.png (preprocessed)")
print("\nOpen these files to see the difference!")
print("="*70)

