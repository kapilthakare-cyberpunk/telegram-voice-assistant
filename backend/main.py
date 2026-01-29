"""
ChatEasezy Backend - FastAPI + Telethon
Personal Telegram messaging assistant with grammar correction
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import os
from pathlib import Path

from telegram_client import TelegramService
from grammar_fixer import GrammarFixer

app = FastAPI(
    title="ChatEasezy API",
    description="Personal Telegram assistant with AI grammar correction",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config paths
CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "./data/config.json"))
SESSION_PATH = Path(os.getenv("SESSION_PATH", "./data/chateaszy.session"))

# Initialize services
telegram_service: Optional[TelegramService] = None
grammar_fixer: Optional[GrammarFixer] = None


def load_config() -> dict:
    """Load configuration from JSON file"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"contacts": {}, "aliases": {}, "settings": {}}


def save_config(config: dict):
    """Save configuration to JSON file"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


# Request/Response models
class SendMessageRequest(BaseModel):
    raw_text: str  # Speech-to-text transcription
    recipient: Optional[str] = None  # Optional explicit recipient
    fix_grammar: bool = True


class SendMessageResponse(BaseModel):
    success: bool
    original_text: str
    corrected_text: str
    recipient: str
    recipient_name: str
    message_id: Optional[int] = None
    error: Optional[str] = None


class ContactCreate(BaseModel):
    name: str
    telegram: str  # Username or phone
    role: str = "colleague"
    aliases: list[str] = []
    notes: str = ""


class ContactResponse(BaseModel):
    id: str
    name: str
    telegram: str
    role: str
    aliases: list[str]
    notes: str


class AuthRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str


class AuthCodeRequest(BaseModel):
    code: str
    password: Optional[str] = None  # 2FA if needed


class HealthResponse(BaseModel):
    status: str
    telegram_connected: bool
    grammar_ai: str


# Startup/Shutdown events
@app.on_event("startup")
async def startup():
    global telegram_service, grammar_fixer
    
    config = load_config()
    
    # Initialize grammar fixer
    grammar_fixer = GrammarFixer()
    
    # Initialize Telegram if credentials exist
    creds = config.get("telegram_credentials")
    if creds and SESSION_PATH.exists():
        telegram_service = TelegramService(
            api_id=creds["api_id"],
            api_hash=creds["api_hash"],
            session_path=str(SESSION_PATH)
        )
        await telegram_service.connect()


@app.on_event("shutdown")
async def shutdown():
    if telegram_service:
        await telegram_service.disconnect()


# Health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        telegram_connected=telegram_service is not None and telegram_service.is_connected,
        grammar_ai=grammar_fixer.active_provider if grammar_fixer else "none"
    )


# Authentication endpoints
@app.post("/auth/start")
async def start_auth(request: AuthRequest):
    """Start Telegram authentication - sends code to phone"""
    global telegram_service
    
    telegram_service = TelegramService(
        api_id=request.api_id,
        api_hash=request.api_hash,
        session_path=str(SESSION_PATH)
    )
    
    result = await telegram_service.start_auth(request.phone)
    
    if result["success"]:
        # Save credentials
        config = load_config()
        config["telegram_credentials"] = {
            "api_id": request.api_id,
            "api_hash": request.api_hash,
            "phone": request.phone
        }
        save_config(config)
    
    return result


@app.post("/auth/complete")
async def complete_auth(request: AuthCodeRequest):
    """Complete authentication with verification code"""
    if not telegram_service:
        raise HTTPException(status_code=400, detail="Start auth first")
    
    result = await telegram_service.complete_auth(request.code, request.password)
    return result


@app.get("/auth/status")
async def auth_status():
    """Check current authentication status"""
    if not telegram_service:
        return {"authenticated": False, "user": None}
    
    user = await telegram_service.get_me()
    return {
        "authenticated": user is not None,
        "user": user
    }


# Messaging endpoints
@app.post("/message/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """Parse, correct, and send a message"""
    if not telegram_service or not telegram_service.is_connected:
        raise HTTPException(status_code=503, detail="Telegram not connected")
    
    config = load_config()
    
    # Fix grammar if requested
    corrected_text = request.raw_text
    recipient_hint = request.recipient
    
    if request.fix_grammar and grammar_fixer:
        result = grammar_fixer.fix_and_parse(request.raw_text, list(config.get("contacts", {}).keys()))
        corrected_text = result["corrected_text"]
        if not recipient_hint:
            recipient_hint = result.get("detected_recipient")
    
    # Resolve recipient
    recipient_info = resolve_recipient(recipient_hint, config)
    if not recipient_info:
        return SendMessageResponse(
            success=False,
            original_text=request.raw_text,
            corrected_text=corrected_text,
            recipient="",
            recipient_name="",
            error=f"Could not find recipient: {recipient_hint}"
        )
    
    # Extract just the message content (remove "send to X" prefix if present)
    message_text = extract_message_content(corrected_text, recipient_info["name"])
    
    # Send via Telegram
    try:
        msg_id = await telegram_service.send_message(
            recipient_info["telegram"],
            message_text
        )
        return SendMessageResponse(
            success=True,
            original_text=request.raw_text,
            corrected_text=message_text,
            recipient=recipient_info["telegram"],
            recipient_name=recipient_info["name"],
            message_id=msg_id
        )
    except Exception as e:
        return SendMessageResponse(
            success=False,
            original_text=request.raw_text,
            corrected_text=message_text,
            recipient=recipient_info["telegram"],
            recipient_name=recipient_info["name"],
            error=str(e)
        )


@app.post("/message/preview")
async def preview_message(request: SendMessageRequest):
    """Preview corrected message without sending"""
    config = load_config()
    
    corrected_text = request.raw_text
    recipient_hint = request.recipient
    
    if request.fix_grammar and grammar_fixer:
        result = grammar_fixer.fix_and_parse(request.raw_text, list(config.get("contacts", {}).keys()))
        corrected_text = result["corrected_text"]
        if not recipient_hint:
            recipient_hint = result.get("detected_recipient")
    
    recipient_info = resolve_recipient(recipient_hint, config)
    message_text = extract_message_content(corrected_text, recipient_info["name"] if recipient_info else "")
    
    return {
        "original": request.raw_text,
        "corrected": message_text,
        "recipient": recipient_info,
        "ready_to_send": recipient_info is not None
    }


# Contact management endpoints
@app.get("/contacts", response_model=list[ContactResponse])
async def list_contacts():
    """List all contacts"""
    config = load_config()
    contacts = []
    
    for contact_id, data in config.get("contacts", {}).items():
        # Find aliases for this contact
        aliases = [k for k, v in config.get("aliases", {}).items() if v == contact_id]
        contacts.append(ContactResponse(
            id=contact_id,
            name=data["name"],
            telegram=data["telegram"],
            role=data.get("role", "colleague"),
            aliases=aliases,
            notes=data.get("notes", "")
        ))
    
    return contacts


@app.post("/contacts", response_model=ContactResponse)
async def create_contact(contact: ContactCreate):
    """Add a new contact"""
    config = load_config()
    
    # Generate ID from name
    contact_id = contact.name.lower().replace(" ", "_")
    
    # Add contact
    if "contacts" not in config:
        config["contacts"] = {}
    
    config["contacts"][contact_id] = {
        "name": contact.name,
        "telegram": contact.telegram,
        "role": contact.role,
        "notes": contact.notes
    }
    
    # Add aliases
    if "aliases" not in config:
        config["aliases"] = {}
    
    config["aliases"][contact.name.lower()] = contact_id
    config["aliases"][contact_id] = contact_id
    for alias in contact.aliases:
        config["aliases"][alias.lower()] = contact_id
    
    save_config(config)
    
    return ContactResponse(
        id=contact_id,
        name=contact.name,
        telegram=contact.telegram,
        role=contact.role,
        aliases=[contact.name.lower()] + contact.aliases,
        notes=contact.notes
    )


@app.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str):
    """Delete a contact"""
    config = load_config()
    
    if contact_id not in config.get("contacts", {}):
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Remove contact
    del config["contacts"][contact_id]
    
    # Remove aliases pointing to this contact
    config["aliases"] = {k: v for k, v in config.get("aliases", {}).items() if v != contact_id}
    
    save_config(config)
    return {"success": True}


# Helper functions
def resolve_recipient(hint: Optional[str], config: dict) -> Optional[dict]:
    """Resolve a recipient hint to contact info"""
    if not hint:
        return None
    
    hint_lower = hint.lower().strip()
    
    # Check if it's a direct @username
    if hint.startswith("@"):
        return {"name": hint, "telegram": hint}
    
    # Check aliases
    aliases = config.get("aliases", {})
    if hint_lower in aliases:
        contact_id = aliases[hint_lower]
        contact = config.get("contacts", {}).get(contact_id)
        if contact:
            return contact
    
    # Check contact names directly
    for contact_id, contact in config.get("contacts", {}).items():
        if contact["name"].lower() == hint_lower:
            return contact
    
    return None


def extract_message_content(text: str, recipient_name: str) -> str:
    """Extract the actual message content, removing addressing prefixes"""
    import re
    
    # Common patterns to remove
    patterns = [
        rf"(?i)^(send|message|tell|text)\s+(to\s+)?{re.escape(recipient_name)}\s*(that|saying|:)?\s*",
        rf"(?i)^(send|message|tell|text)\s+(to\s+)?@\w+\s*(that|saying|:)?\s*",
        r"(?i)^(hey|hi|hello)\s+\w+\s*,?\s*",
    ]
    
    result = text
    for pattern in patterns:
        result = re.sub(pattern, "", result, count=1)
    
    return result.strip()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
