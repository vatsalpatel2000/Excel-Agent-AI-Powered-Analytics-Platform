"""
Session State - State Management for Chat Sessions

Manages session-level state including:
- Active file IDs
- Current context
- User preferences
- Redis-ready for production scaling
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import threading


@dataclass
class SessionData:
    """Data for a single session."""
    chat_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    # File context
    active_file_ids: List[str] = field(default_factory=list)
    current_sheet: Optional[str] = None
    
    # User preferences
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chat_id": self.chat_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "active_file_ids": self.active_file_ids,
            "current_sheet": self.current_sheet,
            "preferences": self.preferences,
            "metadata": self.metadata,
        }


class SessionState:
    """
    Session state manager.
    
    In-memory implementation with Redis-ready interface.
    For production, swap implementation to RedisSessionState.
    """
    
    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        self._lock = threading.RLock()
    
    def get_or_create(self, chat_id: str) -> SessionData:
        """Get or create session for a chat."""
        with self._lock:
            if chat_id not in self._sessions:
                self._sessions[chat_id] = SessionData(chat_id=chat_id)
            else:
                self._sessions[chat_id].update_activity()
            return self._sessions[chat_id]
    
    def get(self, chat_id: str) -> Optional[SessionData]:
        """Get session if exists."""
        with self._lock:
            return self._sessions.get(chat_id)
    
    def update(self, chat_id: str, **kwargs) -> SessionData:
        """Update session data."""
        with self._lock:
            session = self.get_or_create(chat_id)
            
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            
            session.update_activity()
            return session
    
    def add_file(self, chat_id: str, file_id: str) -> SessionData:
        """Add a file to session."""
        session = self.get_or_create(chat_id)
        if file_id not in session.active_file_ids:
            session.active_file_ids.append(file_id)
        session.update_activity()
        return session
    
    def set_current_sheet(self, chat_id: str, sheet_name: str) -> SessionData:
        """Set the current active sheet."""
        session = self.get_or_create(chat_id)
        session.current_sheet = sheet_name
        session.update_activity()
        return session
    
    def set_preference(self, chat_id: str, key: str, value: Any) -> SessionData:
        """Set a user preference."""
        session = self.get_or_create(chat_id)
        session.preferences[key] = value
        session.update_activity()
        return session
    
    def delete(self, chat_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if chat_id in self._sessions:
                del self._sessions[chat_id]
                # Also delete persisted file
                self._delete_session_file(chat_id)
                return True
            return False
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        with self._lock:
            return list(self._sessions.keys())
    
    # =========================================================================
    # Session Persistence (for page reload recovery)
    # =========================================================================
    
    def save_state(self, chat_id: str) -> bool:
        """Serialize and persist session state to pickle file."""
        from app.config import settings
        import pickle
        from pathlib import Path
        
        if not settings.SESSION_PERSISTENCE_ENABLED:
            return False
        
        session = self.get(chat_id)
        if not session:
            return False
        
        try:
            cache_dir = Path(settings.SESSION_CACHE_DIR)
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            session_file = cache_dir / f"{chat_id}.pkl"
            
            with open(session_file, 'wb') as f:
                pickle.dump(session.to_dict(), f)
            
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to save session {chat_id}: {e}")
            return False
    
    def load_state(self, chat_id: str) -> bool:
        """Restore session state from persistence."""
        from app.config import settings
        import pickle
        from pathlib import Path
        
        if not settings.SESSION_PERSISTENCE_ENABLED:
            return False
        
        try:
            cache_dir = Path(settings.SESSION_CACHE_DIR)
            session_file = cache_dir / f"{chat_id}.pkl"
            
            if not session_file.exists():
                return False
            
            with open(session_file, 'rb') as f:
                data = pickle.load(f)
            
            # Reconstruct session
            session = SessionData(
                chat_id=data['chat_id'],
                created_at=datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at'],
                last_activity=datetime.fromisoformat(data['last_activity']) if isinstance(data['last_activity'], str) else data['last_activity'],
                active_file_ids=data.get('active_file_ids', []),
                current_sheet=data.get('current_sheet'),
                preferences=data.get('preferences', {}),
                metadata=data.get('metadata', {}),
            )
            
            with self._lock:
                self._sessions[chat_id] = session
            
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load session {chat_id}: {e}")
            return False
    
    def _delete_session_file(self, chat_id: str) -> None:
        """Delete the session persistence file."""
        from app.config import settings
        from pathlib import Path
        
        try:
            cache_dir = Path(settings.SESSION_CACHE_DIR)
            session_file = cache_dir / f"{chat_id}.pkl"
            if session_file.exists():
                session_file.unlink()
        except Exception:
            pass
    
    def restore_or_create(self, chat_id: str) -> SessionData:
        """Try to restore session from disk, or create new one."""
        with self._lock:
            if chat_id in self._sessions:
                self._sessions[chat_id].update_activity()
                return self._sessions[chat_id]
        
        # Try to restore from disk
        if self.load_state(chat_id):
            return self._sessions[chat_id]
        
        # Create new session
        return self.get_or_create(chat_id)


# Singleton
_session_state: Optional[SessionState] = None
_state_lock = threading.Lock()


def get_session_state() -> SessionState:
    """Get the singleton SessionState instance."""
    global _session_state
    if _session_state is None:
        with _state_lock:
            if _session_state is None:
                _session_state = SessionState()
    return _session_state

