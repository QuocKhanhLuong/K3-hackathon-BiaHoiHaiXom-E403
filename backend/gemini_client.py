"""
Google Gemini AI Integration Helper for VLearn Tutor Tools
Target Models: gemini-3.1-flash-lite | gemini-3-flash | gemini-2.5-flash
"""
import os
import json
from typing import Optional, Any

# Preferred Gemini models in priority order
GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash"
]

def call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    json_mode: bool = False,
    api_key: Optional[str] = None
) -> Optional[str]:
    """
    Calls Google Gemini Flash model with automatic model fallback and error handling.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=key)

        for model_name in GEMINI_MODELS:
            try:
                generation_config = {}
                if json_mode:
                    generation_config["response_mime_type"] = "application/json"

                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction,
                    generation_config=generation_config
                )

                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                # Try next fallback model if specific model fails
                continue
    except Exception as err:
        print(f"[Gemini Client] Warning: API call failed: {err}")

    return None

def call_gemini_json(
    prompt: str,
    system_instruction: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[dict]:
    """
    Calls Gemini and parses JSON output safely.
    """
    raw_text = call_gemini(prompt, system_instruction=system_instruction, json_mode=True, api_key=api_key)
    if not raw_text:
        return None

    try:
        # Clean markdown codeblocks if present
        clean = raw_text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return json.loads(clean.strip())
    except Exception as e:
        print(f"[Gemini Client] JSON parse error: {e}")
        return None
