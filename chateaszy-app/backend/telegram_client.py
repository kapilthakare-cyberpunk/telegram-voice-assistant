"""
Telegram Client Service - Telethon wrapper for ChatEasezy
Handles authentication and message sending via StringSession
"""

import asyncio
import os
from typing import Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.types import User


class TelegramService:
    def __init__(self, api_id: int, api_hash: str, session_string: Optional[str] = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string or ""
        self.client: Optional[TelegramClient] = None
        self.phone: Optional[str] = None
        self.phone_code_hash: Optional[str] = None
        self._is_connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected and self.client is not None
    
    async def connect(self):
        """Connect to Telegram using StringSession"""
        if self.client is None:
            self.client = TelegramClient(
                StringSession(self.session_string),
                self.api_id,
                self.api_hash
            )
        
        await self.client.connect()
        
        if await self.client.is_user_authorized():
            self._is_connected = True
            return True
        
        return False
    
    async def disconnect(self):
        """Disconnect from Telegram"""
        if self.client:
            await self.client.disconnect()
            self._is_connected = False
    
    async def start_auth(self, phone: str) -> dict:
        """Start authentication process - sends verification code"""
        try:
            if self.client is None:
                self.client = TelegramClient(
                    StringSession(self.session_string),
                    self.api_id,
                    self.api_hash
                )
            
            await self.client.connect()
            
            # Check if already authorized
            if await self.client.is_user_authorized():
                user = await self.client.get_me()
                self._is_connected = True
                return {
                    "success": True,
                    "already_authorized": True,
                    "user": {
                        "id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "username": user.username
                    }
                }
            
            # Send code
            self.phone = phone
            result = await self.client.send_code_request(phone)
            self.phone_code_hash = result.phone_code_hash
            
            return {
                "success": True,
                "already_authorized": False,
                "code_sent": True,
                "message": "Verification code sent to your Telegram app"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def complete_auth(self, code: str, password: Optional[str] = None) -> dict:
        """Complete authentication with verification code"""
        try:
            if not self.client or not self.phone or not self.phone_code_hash:
                return {
                    "success": False,
                    "error": "Auth not started. Call start_auth first."
                }
            
            try:
                await self.client.sign_in(
                    phone=self.phone,
                    code=code,
                    phone_code_hash=self.phone_code_hash
                )
            except SessionPasswordNeededError:
                # 2FA is enabled
                if not password:
                    return {
                        "success": False,
                        "needs_2fa": True,
                        "error": "Two-factor authentication is enabled. Please provide your password."
                    }
                await self.client.sign_in(password=password)
            except PhoneCodeInvalidError:
                return {
                    "success": False,
                    "error": "Invalid verification code. Please try again."
                }
            
            user = await self.client.get_me()
            self._is_connected = True
            
            # Get new session string for storage
            new_session_string = self.client.session.save()
            
            return {
                "success": True,
                "session_string": new_session_string,
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "phone": user.phone
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_me(self) -> Optional[dict]:
        """Get current user info"""
        if not self.client or not await self.client.is_user_authorized():
            return None
        
        user = await self.client.get_me()
        return {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone": user.phone
        }
    
    async def send_message(self, recipient: str, message: str) -> int:
        """
        Send a message to a recipient
        
        Args:
            recipient: Username (@username) or phone number
            message: Message text to send
        
        Returns:
            Message ID
        """
        if not self.client or not self._is_connected:
            raise RuntimeError("Not connected to Telegram")
        
        # Resolve recipient
        entity = await self.client.get_entity(recipient)
        
        # Send message
        result = await self.client.send_message(entity, message)
        
        return result.id
    
    async def get_dialogs(self, limit: int = 20) -> list:
        """Get recent chats/dialogs for contact suggestions"""
        if not self.client or not self._is_connected:
            return []
        
        dialogs = await self.client.get_dialogs(limit=limit)
        
        result = []
        for dialog in dialogs:
            entity = dialog.entity
            if isinstance(entity, User):
                result.append({
                    "id": entity.id,
                    "name": f"{entity.first_name or ''} {entity.last_name or ''}".strip(),
                    "username": entity.username,
                    "phone": entity.phone
                })
        
        return result
    
    async def resolve_username(self, username: str) -> Optional[dict]:
        """Resolve a username to user info"""
        try:
            entity = await self.client.get_entity(username)
            if isinstance(entity, User):
                return {
                    "id": entity.id,
                    "name": f"{entity.first_name or ''} {entity.last_name or ''}".strip(),
                    "username": entity.username
                }
        except Exception:
            pass
        return None
