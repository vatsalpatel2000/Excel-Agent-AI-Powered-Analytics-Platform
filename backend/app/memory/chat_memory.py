"""
Chat Memory - Conversation History Management

Maintains conversation history for:
- Context in follow-up questions
- Session reconstruction on page reload
- Audit trail
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading


class MessageRole(Enum):
    """Role of message in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    """A single message in conversation history."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class FileContext:
    """File context stored in memory."""
    file_id: str
    file_name: str
    sheets: List[Dict[str, Any]]
    uploaded_at: datetime = field(default_factory=datetime.utcnow)


class ChatMemory:
    """
    Manages conversation history for a chat session - Production Grade.
    
    Features:
    - Message history with file persistence
    - File context
    - Iteration context for follow-ups
    - Session reconstruction for page reload
    - Max message limit to prevent context overflow
    """
    
    MAX_MESSAGES = 200  # Production-grade message retention
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self._messages: List[ChatMessage] = []
        self._file_context: Optional[FileContext] = None
        self._lock = threading.RLock()
    
    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> None:
        """Add a user message."""
        self._add_message("user", content, metadata)
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> None:
        """Add an assistant message."""
        self._add_message("assistant", content, metadata)
    
    def add_system_message(self, content: str) -> None:
        """Add a system message."""
        self._add_message("system", content)
    
    def _add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Add a message to history."""
        with self._lock:
            message = ChatMessage(
                role=role,
                content=content,
                metadata=metadata or {},
            )
            self._messages.append(message)
            
            # Prune old messages if over limit
            if len(self._messages) > self.MAX_MESSAGES:
                # Keep system messages and recent messages
                system_msgs = [m for m in self._messages if m.role == "system"]
                other_msgs = [m for m in self._messages if m.role != "system"]
                self._messages = system_msgs + other_msgs[-(self.MAX_MESSAGES - len(system_msgs)):]
    
    def get_messages(self, limit: Optional[int] = None) -> List[ChatMessage]:
        """Get messages, optionally limited."""
        with self._lock:
            if limit:
                return self._messages[-limit:]
            return list(self._messages)
    
    def get_messages_for_llm(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get messages formatted for LLM API."""
        messages = self.get_messages(limit)
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def set_file_context(
        self,
        file_id: str,
        file_name: str,
        sheets: List[Dict[str, Any]],
    ) -> None:
        """Set the current file context."""
        with self._lock:
            self._file_context = FileContext(
                file_id=file_id,
                file_name=file_name,
                sheets=sheets,
            )
    
    def get_file_context(self) -> Optional[FileContext]:
        """Get current file context."""
        return self._file_context
    
    def get_context_summary(self) -> str:
        """Get a summary of current context."""
        lines = []
        
        if self._file_context:
            lines.append(f"File: {self._file_context.file_name}")
            lines.append(f"Sheets: {len(self._file_context.sheets)}")
            for sheet in self._file_context.sheets:
                lines.append(f"  - {sheet.get('name', 'Unknown')}: {sheet.get('row_count', 0)} rows")
        else:
            lines.append("No file loaded")
        
        lines.append(f"Messages in history: {len(self._messages)}")
        
        return "\n".join(lines)
    
    def get_iteration_context(self) -> str:
        """
        Get context for iterative reasoning.
        Includes recent conversation and file info.
        """
        lines = ["## Conversation Context"]
        
        # Recent messages
        recent = self.get_messages(limit=5)
        for msg in recent:
            role_label = "User" if msg.role == "user" else "Assistant"
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            lines.append(f"- **{role_label}**: {content}")
        
        # File context
        if self._file_context:
            lines.append("")
            lines.append("## Active File")
            lines.append(f"- Name: {self._file_context.file_name}")
            lines.append(f"- Sheets: {len(self._file_context.sheets)}")
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Clear all messages."""
        with self._lock:
            self._messages = []
            self._file_context = None
            self._delete_cache_file()
    
    # =========================================================================
    # Persistence Methods (for page reload recovery)
    # =========================================================================
    
    def save_to_file(self) -> bool:
        """Persist chat memory to disk."""
        from app.config import settings
        import pickle
        from pathlib import Path
        
        if not settings.SESSION_PERSISTENCE_ENABLED:
            return False
        
        try:
            cache_dir = Path(settings.SESSION_CACHE_DIR)
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            cache_file = cache_dir / f"memory_{self.chat_id}.pkl"
            
            data = {
                "chat_id": self.chat_id,
                "messages": [m.to_dict() for m in self._messages],
                "file_context": {
                    "file_id": self._file_context.file_id,
                    "file_name": self._file_context.file_name,
                    "sheets": self._file_context.sheets,
                    "uploaded_at": self._file_context.uploaded_at.isoformat(),
                } if self._file_context else None,
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to save chat memory {self.chat_id}: {e}")
            return False
    
    def load_from_file(self) -> bool:
        """Load chat memory from disk."""
        from app.config import settings
        import pickle
        from pathlib import Path
        
        if not settings.SESSION_PERSISTENCE_ENABLED:
            return False
        
        try:
            cache_dir = Path(settings.SESSION_CACHE_DIR)
            cache_file = cache_dir / f"memory_{self.chat_id}.pkl"
            
            if not cache_file.exists():
                return False
            
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            with self._lock:
                # Reconstruct messages
                self._messages = []
                for m in data.get("messages", []):
                    self._messages.append(ChatMessage(
                        role=m["role"],
                        content=m["content"],
                        timestamp=datetime.fromisoformat(m["timestamp"]) if isinstance(m.get("timestamp"), str) else datetime.utcnow(),
                        metadata=m.get("metadata", {}),
                    ))
                
                # Reconstruct file context
                fc = data.get("file_context")
                if fc:
                    self._file_context = FileContext(
                        file_id=fc["file_id"],
                        file_name=fc["file_name"],
                        sheets=fc["sheets"],
                        uploaded_at=datetime.fromisoformat(fc["uploaded_at"]) if isinstance(fc.get("uploaded_at"), str) else datetime.utcnow(),
                    )
            
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load chat memory {self.chat_id}: {e}")
            return False
    
    def _delete_cache_file(self) -> None:
        """Delete cache file on clear."""
        from app.config import settings
        from pathlib import Path
        
        try:
            cache_dir = Path(settings.SESSION_CACHE_DIR)
            cache_file = cache_dir / f"memory_{self.chat_id}.pkl"
            if cache_file.exists():
                cache_file.unlink()
        except Exception:
            pass
    
    def reconstruct_session(self) -> bool:
        """Try to reconstruct session from persisted data."""
        return self.load_from_file()


# Storage for chat memories
_chat_memories: Dict[str, ChatMemory] = {}
_memory_lock = threading.Lock()


def get_chat_memory(chat_id: str, try_restore: bool = True) -> ChatMemory:
    """Get or create ChatMemory for a chat ID, optionally restoring from disk."""
    global _chat_memories
    
    if chat_id not in _chat_memories:
        with _memory_lock:
            if chat_id not in _chat_memories:
                memory = ChatMemory(chat_id)
                # Try to restore from disk
                if try_restore:
                    memory.load_from_file()
                _chat_memories[chat_id] = memory
    
    return _chat_memories[chat_id]
