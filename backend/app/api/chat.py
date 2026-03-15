"""
Chat API Endpoints - Frontend Compatible

Matches the frontend API client expectations:
- POST /api/chat/new
- GET /api/chat/list
- GET /api/chat/{chat_id}
- POST /api/chat/{chat_id}/message
- PATCH /api/chat/{chat_id}/title
- DELETE /api/chat/{chat_id}
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging
import uuid
from datetime import datetime

from app.agent import process_chat_message
from app.memory import get_chat_memory
from app.core import get_sheet_index

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory chat storage (for demo - use database in production)
_chats: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateChatRequest(BaseModel):
    """Request model for creating a new chat."""
    title: Optional[str] = None


class Chat(BaseModel):
    """Chat model matching frontend expectations."""
    id: str
    title: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int = 0


class Message(BaseModel):
    """Message model matching frontend expectations."""
    id: str
    role: str
    content: str
    created_at: str


class ChatHistory(BaseModel):
    """Chat history model matching frontend expectations."""
    chat: Chat
    messages: List[Message]


class SendMessageRequest(BaseModel):
    """Request model for sending a message."""
    content: str


class ChatMessageResponse(BaseModel):
    """Response model for sent message matching frontend expectations."""
    chat_id: str
    user_message: Message
    assistant_message: Message
    content_markdown: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/new", response_model=Chat)
async def create_chat(request: CreateChatRequest):
    """Create a new chat session."""
    chat_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    
    chat = {
        "id": chat_id,
        "title": request.title or "New Chat",
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    
    _chats[chat_id] = chat
    
    return Chat(**chat)


@router.get("/list", response_model=List[Chat])
async def list_chats(limit: int = 50, offset: int = 0):
    """List all chat sessions."""
    chats = list(_chats.values())
    # Sort by updated_at descending
    chats.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return [Chat(**c) for c in chats[offset:offset + limit]]


@router.get("/{chat_id}", response_model=ChatHistory)
async def get_chat(chat_id: str):
    """Get a chat with its message history."""
    if chat_id not in _chats:
        # Create chat if it doesn't exist (for backwards compatibility)
        now = datetime.utcnow().isoformat() + "Z"
        _chats[chat_id] = {
            "id": chat_id,
            "title": "New Chat",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }
    
    chat = _chats[chat_id]
    memory = get_chat_memory(chat_id)
    
    messages = []
    for msg in memory.get_messages():
        messages.append(Message(
            id=str(uuid.uuid4()),
            role=msg.role,
            content=msg.content,
            created_at=msg.timestamp.isoformat() + "Z",
        ))
    
    return ChatHistory(
        chat=Chat(**chat),
        messages=messages,
    )


@router.post("/{chat_id}/message", response_model=ChatMessageResponse)
async def send_message(chat_id: str, request: SendMessageRequest):
    """Send a message to a chat and get agent response."""
    try:
        # Create chat if it doesn't exist
        if chat_id not in _chats:
            now = datetime.utcnow().isoformat() + "Z"
            _chats[chat_id] = {
                "id": chat_id,
                "title": "New Chat",
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
            }
        
        memory = get_chat_memory(chat_id)
        now = datetime.utcnow()
        
        # Create user message
        user_msg = Message(
            id=str(uuid.uuid4()),
            role="user",
            content=request.content,
            created_at=now.isoformat() + "Z",
        )
        
        # Add to memory
        memory.add_user_message(request.content)
        
        # Get agent response
        history = memory.get_messages_for_llm(limit=10)
        response = await process_chat_message(
            chat_id=chat_id,
            message=request.content,
            history=history,
        )
        
        # Add assistant response to memory
        memory.add_assistant_message(response)
        
        # Create assistant message
        assistant_msg = Message(
            id=str(uuid.uuid4()),
            role="assistant",
            content=response,
            created_at=datetime.utcnow().isoformat() + "Z",
        )
        
        # Update chat
        _chats[chat_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
        _chats[chat_id]["message_count"] = len(memory.get_messages())
        
        # Auto-generate title from first message
        if _chats[chat_id]["title"] == "New Chat" and request.content:
            _chats[chat_id]["title"] = request.content[:50] + ("..." if len(request.content) > 50 else "")
        
        # Persist memory for session reconstruction on page reload
        memory.save_to_file()
        
        return ChatMessageResponse(
            chat_id=chat_id,
            user_message=user_msg,
            assistant_message=assistant_msg,
            content_markdown=response,
        )
        
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{chat_id}/title")
async def update_chat_title(chat_id: str, title: str):
    """Update a chat's title."""
    if chat_id not in _chats:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    _chats[chat_id]["title"] = title
    _chats[chat_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    
    return {"success": True}


@router.delete("/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a chat and its history."""
    if chat_id in _chats:
        del _chats[chat_id]
    
    # Clear memory
    memory = get_chat_memory(chat_id)
    memory.clear()
    
    return {"success": True}
