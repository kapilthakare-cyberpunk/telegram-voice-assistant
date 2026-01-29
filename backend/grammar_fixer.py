"""
Grammar Fixer - AI-powered grammar correction and message parsing
Supports Groq (Llama) and Google Gemini with automatic fallback
"""

import os
import re
import json
from typing import Optional
import httpx


class GrammarFixer:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self._active_provider = None
        
        # Determine active provider
        if self.groq_api_key:
            self._active_provider = "groq"
        elif self.gemini_api_key:
            self._active_provider = "gemini"
    
    @property
    def active_provider(self) -> str:
        return self._active_provider or "none"
    
    def fix_and_parse(self, text: str, known_contacts: list[str]) -> dict:
        """
        Fix grammar and extract recipient from speech-to-text input
        
        Args:
            text: Raw speech-to-text transcription
            known_contacts: List of known contact names/aliases
        
        Returns:
            {
                "corrected_text": str,
                "detected_recipient": str or None,
                "confidence": float
            }
        """
        if not self._active_provider:
            # No AI available - just do basic cleanup
            return {
                "corrected_text": self._basic_cleanup(text),
                "detected_recipient": self._extract_recipient_basic(text, known_contacts),
                "confidence": 0.5
            }
        
        prompt = self._build_prompt(text, known_contacts)
        
        try:
            if self._active_provider == "groq":
                result = self._call_groq(prompt)
            else:
                result = self._call_gemini(prompt)
            
            return self._parse_ai_response(result, text, known_contacts)
        
        except Exception as e:
            print(f"AI error: {e}")
            # Fallback to basic processing
            return {
                "corrected_text": self._basic_cleanup(text),
                "detected_recipient": self._extract_recipient_basic(text, known_contacts),
                "confidence": 0.5,
                "error": str(e)
            }
    
    def _build_prompt(self, text: str, known_contacts: list[str]) -> str:
        contacts_str = ", ".join(known_contacts) if known_contacts else "none specified"
        
        return f"""You are a grammar correction assistant for a messaging app. 
Your task is to:
1. Fix any grammar, spelling, or punctuation errors in the transcribed speech
2. Identify who the message should be sent to
3. Extract just the message content (remove "send to X" prefix)

Known contacts: {contacts_str}

Input (speech-to-text transcription):
"{text}"

Respond in JSON format only:
{{
    "corrected_message": "the corrected message content only (not including 'send to X' prefix)",
    "recipient": "detected recipient name or null if unclear",
    "confidence": 0.0-1.0
}}

Examples:
- Input: "send message to rahul saying hey can you send me teh files tommorow"
  Output: {{"corrected_message": "Hey, can you send me the files tomorrow?", "recipient": "rahul", "confidence": 0.95}}

- Input: "tell my boss that the meeting went good and we closed the deal"  
  Output: {{"corrected_message": "The meeting went well and we closed the deal.", "recipient": "boss", "confidence": 0.9}}

Now process the input above:"""
    
    def _call_groq(self, prompt: str) -> str:
        """Call Groq API (Llama model)"""
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",  # Fast and free-tier friendly
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API"""
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 500
                }
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    
    def _parse_ai_response(self, response: str, original_text: str, known_contacts: list[str]) -> dict:
        """Parse AI response and extract structured data"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "corrected_text": data.get("corrected_message", self._basic_cleanup(original_text)),
                    "detected_recipient": data.get("recipient"),
                    "confidence": data.get("confidence", 0.8)
                }
        except (json.JSONDecodeError, KeyError):
            pass
        
        # Fallback if parsing fails
        return {
            "corrected_text": self._basic_cleanup(original_text),
            "detected_recipient": self._extract_recipient_basic(original_text, known_contacts),
            "confidence": 0.5
        }
    
    def _basic_cleanup(self, text: str) -> str:
        """Basic text cleanup without AI"""
        # Capitalize first letter
        text = text.strip()
        if text:
            text = text[0].upper() + text[1:]
        
        # Add period if no ending punctuation
        if text and text[-1] not in '.!?':
            text += '.'
        
        # Fix common speech-to-text errors
        replacements = {
            " im ": " I'm ",
            " i ": " I ",
            " dont ": " don't ",
            " cant ": " can't ",
            " wont ": " won't ",
            " didnt ": " didn't ",
            " doesnt ": " doesn't ",
            " isnt ": " isn't ",
            " arent ": " aren't ",
            " wasnt ": " wasn't ",
            " werent ": " weren't ",
            " youre ": " you're ",
            " theyre ": " they're ",
            " hes ": " he's ",
            " shes ": " she's ",
            " its ": " it's ",  # Context dependent, but often correct
            " weve ": " we've ",
            " ive ": " I've ",
            " teh ": " the ",
            " taht ": " that ",
            " wiht ": " with ",
            " tommorow ": " tomorrow ",
            " tommorrow ": " tomorrow ",
        }
        
        text_lower = f" {text.lower()} "
        for old, new in replacements.items():
            if old in text_lower:
                # Preserve some capitalization
                text = re.sub(re.escape(old.strip()), new.strip(), text, flags=re.IGNORECASE)
        
        return text
    
    def _extract_recipient_basic(self, text: str, known_contacts: list[str]) -> Optional[str]:
        """Extract recipient using pattern matching"""
        text_lower = text.lower()
        
        # Check for @username
        username_match = re.search(r'@(\w+)', text)
        if username_match:
            return f"@{username_match.group(1)}"
        
        # Check for known contacts
        for contact in known_contacts:
            if contact.lower() in text_lower:
                return contact
        
        # Check for common patterns
        patterns = [
            r"(?:send|message|tell|text)\s+(?:to\s+)?(\w+)",
            r"(?:my\s+)?(boss|manager|lead)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1)
        
        return None


# Simple test
if __name__ == "__main__":
    fixer = GrammarFixer()
    
    test_inputs = [
        "send message to rahul saying hey can you send me teh files tommorow",
        "tell my boss that the meeting went good and we closed the deal",
        "message @priya_designs the mockups look great lets finalize them",
    ]
    
    for text in test_inputs:
        result = fixer.fix_and_parse(text, ["rahul", "priya", "boss"])
        print(f"\nInput: {text}")
        print(f"Output: {result}")
