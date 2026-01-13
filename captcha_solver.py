"""
Captcha Solver using Gemini AI
"""

import base64
from google import genai


class CaptchaSolver:
    """Solve captcha using Gemini AI"""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    def solve(self, image_bytes: bytes) -> str:
        """Send captcha image to Gemini and get the text"""
        print("[CAPTCHA] Sending to Gemini AI...")
        
        # Convert to base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_b64
                            }
                        },
                        {
                            "text": "This is a CAPTCHA image. Read the numbers/letters shown. Return ONLY the plain digits and letters, nothing else. Use regular ASCII characters only (0-9, a-z, A-Z). No subscripts, superscripts, or special characters. Just the raw captcha text."
                        }
                    ]
                }
            ]
        )
        
        captcha_text = response.text.strip()
        print(f"[CAPTCHA] Gemini says: '{captcha_text}'")
        
        # Clean up the response
        captcha_text = self._clean_captcha(captcha_text)
        
        return captcha_text
    
    def _clean_captcha(self, text: str) -> str:
        """Clean captcha text - only keep ASCII alphanumeric"""
        # Map of special unicode digits to normal digits
        digit_map = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
            '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
            'θ': '0', 'O': '0', 'o': '0',
        }
        
        cleaned = ""
        for c in text:
            if c in digit_map:
                cleaned += digit_map[c]
            elif c.isascii() and c.isalnum():
                cleaned += c
        
        return cleaned
