"""
Test Session Reuse Pattern locally
After scraping a record, click "RURAL LAND RECORD" to go back
District/Taluka stay selected - just change village!
"""
import os, sys, json, time, re, base64
from datetime import datetime
from playwright.sync_api import sync_playwright
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")

# Test with Ahmedabad district, first taluka
TEST_DISTRICT = "02"
TEST_TALUKA = "04"
TEST_SURVEY = "3"  # Common survey number
MAX_VILLAGES = 5   # Test with 5 villages

print(f"🚀 Session Reuse Test", flush=True)

client = genai.Client(api_key=GEMINI_API_KEY)

URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"

def solve_captcha(image_bytes):
    """Solve captcha using Gemini"""
    print("    [CAPTCHA] Sending to Gemini...", flush=True)
    
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                {"text": "This is a CAPTCHA image. Read the numbers/letters shown. Return ONLY the plain digits and letters, nothing else. Use regular ASCII characters only (0-9, a-z, A-Z). No subscripts, superscripts, or special characters. Just the raw captcha text."}
            ]
        }]
    )
    
    raw = response.text.strip()
    print(f"    [CAPTCHA] Raw: '{raw}'", flush=True)
    
    digit_map = {
        '₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9',
        '⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9',
        'θ':'0','O':'0','o':'0'
    }
    cleaned = ""
    for c in raw:
        if c in digit_map:
            cleaned += digit_map[c]
        elif c.isascii() and c.isalnum():
            cleaned += c
    
    print(f"    [CAPTCHA] Cleaned: '{cleaned}'", flush=True)
    return cleaned


def go_back_to_form(page):
    """Click 'RURAL LAND RECORD' link to go back - preserves district/taluka!"""
    try:
        