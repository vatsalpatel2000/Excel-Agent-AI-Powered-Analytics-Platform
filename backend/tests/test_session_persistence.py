"""
Session Persistence Tests

Tests for session state persistence and page reload recovery:
- Session state save/load
- Chat memory persistence
- Session reconstruction
"""

import pytest
import tempfile
import os
from uuid import uuid4
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.memory.session_state import SessionState, SessionData, get_session_state
from app.memory.chat_memory import ChatMemory, get_chat_memory


class TestSessionStatePersistence:
    """Tests for SessionState persistence functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup with temporary directory for persistence."""
        self.temp_dir = tempfile.mkdtemp()
        self.chat_id = str(uuid4())
    
    def teardown_method(self):
        """Cleanup temp files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.config.settings')
    def test_save_and_load_state(self, mock_settings):
        """Test that session state can be saved and loaded."""
        mock_settings.SESSION_PERSISTENCE_ENABLED = True
        mock_settings.SESSION_CACHE_DIR = self.temp_dir
        
        state = SessionState()
        
        # Create session with data
        session = state.get_or_create(self.chat_id)
        session.active_file_ids = ["file1", "file2"]
        session.current_sheet = "Sheet1"
        session.preferences = {"theme": "dark"}
        
        # Save state
        success = state.save_state(self.chat_id)
        assert success is True
        
        # Verify file exists
        cache_file = Path(self.temp_dir) / f"{self.chat_id}.pkl"
        assert cache_file.exists()
        
        # Create new state instance and load
        state2 = SessionState()
        loaded = state2.load_state(self.chat_id)
        assert loaded is True
        
        # Verify data was restored
        restored = state2.get(self.chat_id)
        assert restored is not None
        assert restored.active_file_ids == ["file1", "file2"]
        assert restored.current_sheet == "Sheet1"
        assert restored.preferences == {"theme": "dark"}
    
    @patch('app.config.settings')
    def test_restore_or_create(self, mock_settings):
        """Test restore_or_create functionality."""
        mock_settings.SESSION_PERSISTENCE_ENABLED = True
        mock_settings.SESSION_CACHE_DIR = self.temp_dir
        
        state = SessionState()
        
        # Create and save
        session = state.get_or_create(self.chat_id)
        session.active_file_ids = ["test_file"]
        state.save_state(self.chat_id)
        
        # Clear in-memory state
        state._sessions = {}
        
        # Restore or create should load from disk
        restored = state.restore_or_create(self.chat_id)
        assert restored.active_file_ids == ["test_file"]
    
    @patch('app.config.settings')
    def test_delete_removes_file(self, mock_settings):
        """Test that delete also removes persistence file."""
        mock_settings.SESSION_PERSISTENCE_ENABLED = True
        mock_settings.SESSION_CACHE_DIR = self.temp_dir
        
        state = SessionState()
        state.get_or_create(self.chat_id)
        state.save_state(self.chat_id)
        
        cache_file = Path(self.temp_dir) / f"{self.chat_id}.pkl"
        assert cache_file.exists()
        
        # Delete session
        state.delete(self.chat_id)
        
        # File should be removed
        assert not cache_file.exists()


class TestChatMemoryPersistence:
    """Tests for ChatMemory persistence functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.chat_id = str(uuid4())
    
    def teardown_method(self):
        """Cleanup temp files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.config.settings')
    def test_save_and_load_memory(self, mock_settings):
        """Test that chat memory can be persisted and restored."""
        mock_settings.SESSION_PERSISTENCE_ENABLED = True
        mock_settings.SESSION_CACHE_DIR = self.temp_dir
        
        memory = ChatMemory(self.chat_id)
        
        # Add messages
        memory.add_user_message("What is the revenue?")
        memory.add_assistant_message("The revenue is $1,000,000.")
        memory.add_user_message("How does that compare to last year?")
        memory.add_assistant_message("It's 10% higher than last year.")
        
        # Set file context
        memory.set_file_context(
            file_id="file123",
            file_name="data.xlsx",
            sheets=[{"name": "Sheet1", "row_count": 100}]
        )
        
        # Save
        success = memory.save_to_file()
        assert success is True
        
        # Create new memory instance and load
        memory2 = ChatMemory(self.chat_id)
        loaded = memory2.load_from_file()
        assert loaded is True
        
        # Verify messages restored
        messages = memory2.get_messages()
        assert len(messages) == 4
        assert messages[0].role == "user"
        assert messages[0].content == "What is the revenue?"
        
        # Verify file context restored
        fc = memory2.get_file_context()
        assert fc is not None
        assert fc.file_name == "data.xlsx"
    
    @patch('app.config.settings')
    def test_clear_removes_file(self, mock_settings):
        """Test that clear also removes cache file."""
        mock_settings.SESSION_PERSISTENCE_ENABLED = True
        mock_settings.SESSION_CACHE_DIR = self.temp_dir
        
        memory = ChatMemory(self.chat_id)
        memory.add_user_message("Test message")
        memory.save_to_file()
        
        cache_file = Path(self.temp_dir) / f"memory_{self.chat_id}.pkl"
        assert cache_file.exists()
        
        # Clear
        memory.clear()
        
        # File should be removed
        assert not cache_file.exists()
        
        # Messages should be cleared
        assert len(memory.get_messages()) == 0
    
    @patch('app.config.settings')
    def test_max_messages_limit(self, mock_settings):
        """Test that MAX_MESSAGES limit is enforced."""
        mock_settings.SESSION_PERSISTENCE_ENABLED = True
        mock_settings.SESSION_CACHE_DIR = self.temp_dir
        
        memory = ChatMemory(self.chat_id)
        
        # Add more than MAX_MESSAGES
        for i in range(250):
            memory.add_user_message(f"Message {i}")
        
        # Should be pruned to MAX_MESSAGES
        messages = memory.get_messages()
        assert len(messages) <= memory.MAX_MESSAGES


class TestSessionReconstruction:
    """Tests for full session reconstruction on page reload."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.chat_id = str(uuid4())
    
    def teardown_method(self):
        """Cleanup."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.config.settings')
    def test_reconstruct_session(self, mock_settings):
        """Test full session reconstruction scenario."""
        mock_settings.SESSION_PERSISTENCE_ENABLED = True
        mock_settings.SESSION_CACHE_DIR = self.temp_dir
        
        # Simulate first session
        memory1 = ChatMemory(self.chat_id)
        memory1.add_user_message("Analyze revenue trends")
        memory1.add_assistant_message("I found 3 key trends...")
        memory1.set_file_context("file1", "report.xlsx", [{"name": "Data"}])
        memory1.save_to_file()
        
        # Simulate "page reload" - new memory instance
        memory2 = ChatMemory(self.chat_id)
        
        # Initially empty
        assert len(memory2.get_messages()) == 0
        
        # Reconstruct
        success = memory2.reconstruct_session()
        assert success is True
        
        # Now should have messages
        messages = memory2.get_messages()
        assert len(messages) == 2
        assert "revenue" in messages[0].content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
