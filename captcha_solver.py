"""
Captcha Solver using Gemini AI with API Key Rotation
"""

import base64
import random
from google import genai


# All available Gemini API keys for rotation
GEMINI_API_KEYS = [
    "AIzaSyDWJ5mZH3qyIFA1GS54MbevS_MbjNZys9o",
    "AIzaSyDBkyScEIGGUm2N1JwFrW32CCoAOWTbhXw",
    "AIzaSyCzWYpllqZ2LLK4lscLCFStaT0MwjfjxPw",
    "AIzaSyBJku0hmFZcGUe3e-8DugdcohJ9Y_e8Dk4",
    "AIzaSyC9HwdzLWxNfiH24yd2fIiI4KyMQh3fAHE",
]


class CaptchaSolver:
    """Solve captcha using Gemini AI with rotating API keys"""
    
    def __init__(self, api_key: str = None):
        # Use provided key or pick random from pool
        self.api_keys = GEMINI_API_KEYS.copy()
        self.current_key_index = 0
        self._init_client()
    
    def _init_client(self):
        """Initialize client with current key"""
        key = self.api_keys[self.current_key_index]
        self.client = genai.Client(api_key=key)
    
    def _rotate_key(self):
        """Rotate to next API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self._init_client()
    
    def solve(self, image_bytes: bytes) -> str:
        """Send captcha image to Gemini and get the text"""
        print("[CAPTCHA] Sending to Gemini AI...")
        
        # Convert to base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Try with current key, rotate on failure
        for attempt in range(len(self.api_keys)):
            try:
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
                
                # Rotate key for next request (load balancing)
                self._rotate_key()
                
                return captcha_text
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                    print(f"[CAPTCHA] Rate limited, rotating key...")
                    self._rotate_key()
                    continue
                elif "403" in error_str or "invalid" in error_str.lower():
                    print(f"[CAPTCHA] Key error, rotating...")
                    self._rotate_key()
                    continue
                else:
                    print(f"[CAPTCHA] Error: {e}")
                    self._rotate_key()
                    continue
        
        print("[CAPTCHA] All keys failed")
        return ""
    
    def _clean_captcha(self, text: str) -> str:
        """Clean captcha text - only keep ASCII alphanumeric"""
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
