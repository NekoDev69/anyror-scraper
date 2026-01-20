"""
Captcha Solver - Hybrid Gemini + Vision API
- Rotates 6 Gemini keys to handle rate limits
- Instant fallback to Vision API if Gemini is throttled
- Strict 6-digit numeric validation
"""

import os
import glob
import time
import random
from typing import List, Optional
from google.cloud import vision
from google.oauth2 import service_account
from google import genai
from google.genai import types
from dotenv import load_dotenv

class CaptchaSolver:
    def __init__(self):
        load_dotenv()
        
        # 1. Load Gemini Keys (for rotation)
        self.gemini_keys = self._load_gemini_keys()
        self.current_gemini_index = 0
        
        # 2. Init Vertex AI Gemini (Primary if credentials exist)
        self.vertex_client = self._init_vertex_client()
        
        # 3. Load Vision API (Fallback)
        self.vision_client = self._init_vision_client()
        
        status = "Initialized: "
        if self.vertex_client: status += "Vertex Gemini + "
        status += f"{len(self.gemini_keys)} Gemini keys + Vision API"
        print(f"[CAPTCHA] {status}")

    def _init_vertex_client(self):
        if os.path.exists("vertex-credentials.json"):
            creds_path = "vertex-credentials.json"
        elif os.path.exists("config/vertex-credentials.json"):
            creds_path = "config/vertex-credentials.json"
        else:
            creds_path = None

        if creds_path:
            try:
                # Use the new google-genai SDK for Vertex AI
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(creds_path)
                client = genai.Client(
                    vertexai=True,
                    project="anyror-scraper-2026",
                    location="us-central1"
                )
                return client
            except Exception as e:
                print(f"[CAPTCHA] Failed to init Vertex Gemini: {e}")
        return None

    def _load_gemini_keys(self) -> List[str]:
        keys = []
        if os.getenv("GEMINI_API_KEY"):
            keys.append(os.getenv("GEMINI_API_KEY"))
        for i in range(2, 11):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                keys.append(key)
        return keys

    def _init_vision_client(self):
        creds_path = None
        # Prioritize the new vertex-credentials for vision too if it's the same project
        if os.path.exists("vertex-credentials.json"):
            creds_path = "vertex-credentials.json"
        elif os.path.exists("config/vertex-credentials.json"):
            creds_path = "config/vertex-credentials.json"
        elif os.path.exists("config/vision-credentials.json"):
            creds_path = "config/vision-credentials.json"
        else:
            patterns = ['*vision*.json', '*google*.json', 'credentials*.json', 'config/*.json']
            for pattern in patterns:
                files = glob.glob(pattern)
                if files:
                    creds_path = files[0]
                    break
        
        if not creds_path:
            print("[CAPTCHA] WARNING: Vision API credentials not found!")
            return None
            
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        return vision.ImageAnnotatorClient(credentials=credentials)

    def _clean_captcha(self, text: str) -> str:
        if not text: return ""
        cleaned = text.replace('\n', '').replace(' ', '').replace('-', '').replace('_', '')
        return ''.join(c for c in cleaned if c.isdigit())

    def _solve_with_vertex(self, image_bytes: bytes) -> Optional[str]:
        """Try to solve using Vertex AI Gemini (Premium/Service Account)"""
        if not self.vertex_client:
            return None
            
        try:
            response = self.vertex_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text="Extract the 6 digits from this captcha image. Return JUST the number."),
                            types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                        ]
                    )
                ]
            )
            
            if response.text:
                cleaned = self._clean_captcha(response.text)
                if len(cleaned) == 6:
                    return cleaned
        except Exception as e:
            print(f"[CAPTCHA] Vertex Gemini error: {e}")
        return None

    def _solve_with_gemini_keys(self, image_bytes: bytes) -> Optional[str]:
        """Try to solve using standard Gemini API keys with rotation"""
        if not self.gemini_keys:
            return None
            
        for _ in range(min(3, len(self.gemini_keys))):
            key = self.gemini_keys[self.current_gemini_index]
            try:
                # Use AI Studio client instead of Vertex
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_text(text="Extract the 6 digits from this captcha image. Return JUST the number."),
                                types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                            ]
                        )
                    ]
                )
                
                if response.text:
                    cleaned = self._clean_captcha(response.text)
                    if len(cleaned) == 6:
                        return cleaned
                
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    self.current_gemini_index = (self.current_gemini_index + 1) % len(self.gemini_keys)
                    continue
                print(f"[CAPTCHA] Gemini logic error: {e}")
                break
                
        return None

    def _solve_with_vision(self, image_bytes: bytes) -> Optional[str]:
        """Solid fallback using Vision API"""
        if not self.vision_client:
            return None
        try:
            image = vision.Image(content=image_bytes)
            response = self.vision_client.text_detection(image=image)
            if response.text_annotations:
                cleaned = self._clean_captcha(response.text_annotations[0].description)
                if len(cleaned) == 6:
                    return cleaned
        except Exception as e:
            print(f"[CAPTCHA] Vision error: {e}")
        return None

    def solve(self, image_bytes: bytes, max_attempts: int = 3) -> str:
        """Sequential strategy: Vertex -> API Keys -> Vision"""
        for attempt in range(1, max_attempts + 1):
            # 1. Try Vertex Gemini (Best balance of speed/reliability)
            res = self._solve_with_vertex(image_bytes)
            if res:
                print(f"[CAPTCHA] ✓ Vertex Gemini: '{res}'")
                return res
            
            # 2. Try Standard Gemini Keys (Rotation for volume)
            res = self._solve_with_gemini_keys(image_bytes)
            if res:
                print(f"[CAPTCHA] ✓ Key-based Gemini: '{res}'")
                return res
            
            # 3. Last Resort: Vision API
            print(f"[CAPTCHA] Gemini busy/failed, falling back to Vision...")
            res = self._solve_with_vision(image_bytes)
            if res:
                print(f"[CAPTCHA] ✓ Vision: '{res}'")
                return res
            
            if attempt < max_attempts:
                time.sleep(0.5)
                
        return ""

if __name__ == "__main__":
    s = CaptchaSolver()
    print("✓ Hybrid Solver ready!")
