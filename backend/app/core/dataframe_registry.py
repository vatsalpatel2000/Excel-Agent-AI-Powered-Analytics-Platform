"""
DataFrame Registry - Enhanced Storage for All Loaded DataFrames

Production-grade registry with:
- Thread-safe access via RLock
- Case-insensitive sheet lookup
- Index-based access ("sheet 2", "second sheet")
- Automatic metadata generation
- Optional Redis-backed persistence (future)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
import pandas as pd
import re


@dataclass
class RegisteredDataFrame:
    """Metadata for a registered DataFrame."""
    chat_id: str
    file_id: str
    sheet_name: str
    sheet_index: int  # 0-indexed internally
    file_name: Optional[str] = None
    row_count: int = 0
    column_count: int = 0
    columns: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        chat_id: str,
        file_id: str,
        sheet_name: str,
        sheet_index: int,
        file_name: Optional[str] = None,
    ) -> "RegisteredDataFrame":
        """Create registration metadata from a DataFrame."""
        return cls(
            chat_id=chat_id,
            file_id=file_id,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
            file_name=file_name,
            row_count=len(df),
            column_count=len(df.columns),
            columns=list(df.columns.astype(str)),
        )


class DataFrameRegistry:
    """
    Thread-safe registry for all loaded DataFrames.
    
    Key features:
    - O(1) lookup by chat_id + sheet_name
    - Case-insensitive sheet name matching
    - Index-based access ("sheet 2")
    - Ordinal parsing ("second sheet")
    - Full sheet listing per chat
    """
    
    # Ordinal mappings for natural language
    ORDINALS = {
        "first": 1, "1st": 1,
        "second": 2, "2nd": 2,
        "third": 3, "3rd": 3,
        "fourth": 4, "4th": 4,
        "fifth": 5, "5th": 5,
        "sixth": 6, "6th": 6,
        "seventh": 7, "7th": 7,
        "eighth": 8, "8th": 8,
        "ninth": 9, "9th": 9,
        "tenth": 10, "10th": 10,
    }
    
    def __init__(self):
        # Structure: {chat_id: {sheet_name: (DataFrame, RegisteredDataFrame)}}
        self._registry: Dict[str, Dict[str, Tuple[pd.DataFrame, RegisteredDataFrame]]] = {}
        self._lock = threading.RLock()
    
    def register(
        self,
        chat_id: str,
        file_id: str,
        sheet_name: str,
        dataframe: pd.DataFrame,
        sheet_index: int = 0,
        file_name: Optional[str] = None,
    ) -> RegisteredDataFrame:
        """
        Register a DataFrame for a chat session.
        
        Args:
            chat_id: Unique chat/session identifier
            file_id: Source file identifier
            sheet_name: Name of the sheet
            dataframe: The pandas DataFrame
            sheet_index: Position in multi-sheet file (0-indexed)
            file_name: Original filename
            
        Returns:
            RegisteredDataFrame metadata
        """
        with self._lock:
            if chat_id not in self._registry:
                self._registry[chat_id] = {}
            
            metadata = RegisteredDataFrame.from_dataframe(
                df=dataframe,
                chat_id=chat_id,
                file_id=file_id,
                sheet_name=sheet_name,
                sheet_index=sheet_index,
                file_name=file_name,
            )
            
            self._registry[chat_id][sheet_name] = (dataframe.copy(), metadata)
            
            return metadata
    
    def get(self, chat_id: str, sheet_name: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get a DataFrame by chat and sheet name.
        
        Case-insensitive matching is applied.
        If sheet_name is None, returns first sheet.
        """
        with self._lock:
            if chat_id not in self._registry:
                return None
            
            if sheet_name is None:
                # Return first sheet
                if self._registry[chat_id]:
                    return list(self._registry[chat_id].values())[0][0].copy()
                return None
            
            # Exact match
            if sheet_name in self._registry[chat_id]:
                return self._registry[chat_id][sheet_name][0].copy()
            
            # Case-insensitive match
            sheet_lower = sheet_name.lower()
            for name, (df, _) in self._registry[chat_id].items():
                if name.lower() == sheet_lower:
                    return df.copy()
            
            return None
    
    def get_by_index(self, chat_id: str, index: int) -> Optional[pd.DataFrame]:
        """
        Get DataFrame by 1-based sheet index.
        
        Args:
            chat_id: Chat identifier
            index: 1-based index (for user convenience)
        """
        with self._lock:
            if chat_id not in self._registry:
                return None
            
            target_idx = index - 1  # Convert to 0-indexed
            
            for (df, metadata) in self._registry[chat_id].values():
                if metadata.sheet_index == target_idx:
                    return df.copy()
            
            return None
    
    def get_by_query(self, chat_id: str, query: str) -> Optional[pd.DataFrame]:
        """
        Get DataFrame matching a natural language query.
        
        Handles:
        - "sheet 2", "Sheet2", "sheet #2"
        - "second sheet", "2nd sheet"
        - Partial name matches
        """
        query_lower = query.lower().strip()
        
        # Pattern: "sheet N"
        sheet_num = re.search(r'sheet\s*#?\s*(\d+)', query_lower)
        if sheet_num:
            return self.get_by_index(chat_id, int(sheet_num.group(1)))
        
        # Pattern: ordinals
        for ordinal, num in self.ORDINALS.items():
            if ordinal in query_lower and "sheet" in query_lower:
                return self.get_by_index(chat_id, num)
        
        # Try name match
        return self.get(chat_id, query)
    
    def get_registered(self, chat_id: str, sheet_name: str) -> Optional[RegisteredDataFrame]:
        """Get registration metadata for a sheet."""
        with self._lock:
            if chat_id not in self._registry:
                return None
            
            if sheet_name in self._registry[chat_id]:
                return self._registry[chat_id][sheet_name][1]
            
            # Case-insensitive
            sheet_lower = sheet_name.lower()
            for name, (_, metadata) in self._registry[chat_id].items():
                if name.lower() == sheet_lower:
                    return metadata
            
            return None
    
    def get_all_sheets(self, chat_id: str) -> List[str]:
        """Get all sheet names for a chat, sorted by index."""
        with self._lock:
            if chat_id not in self._registry:
                return []
            
            # Sort by sheet_index
            sheets = sorted(
                self._registry[chat_id].items(),
                key=lambda x: x[1][1].sheet_index
            )
            return [name for name, _ in sheets]
    
    def get_all_dataframes(self, chat_id: str) -> Dict[str, pd.DataFrame]:
        """Get all DataFrames for a chat as {sheet_name: DataFrame}."""
        with self._lock:
            if chat_id not in self._registry:
                return {}
            
            return {
                name: df.copy()
                for name, (df, _) in self._registry[chat_id].items()
            }
    
    def get_sheet_count(self, chat_id: str) -> int:
        """Get number of sheets for a chat."""
        with self._lock:
            if chat_id not in self._registry:
                return 0
            return len(self._registry[chat_id])
    
    def get_total_rows(self, chat_id: str) -> int:
        """Get total row count across all sheets."""
        with self._lock:
            if chat_id not in self._registry:
                return 0
            return sum(
                metadata.row_count
                for _, metadata in self._registry[chat_id].values()
            )
    
    def clear_chat(self, chat_id: str) -> int:
        """Clear all DataFrames for a chat. Returns count of cleared sheets."""
        with self._lock:
            if chat_id not in self._registry:
                return 0
            count = len(self._registry[chat_id])
            del self._registry[chat_id]
            return count
    
    def clear_file(self, chat_id: str, file_id: str) -> int:
        """Clear all sheets from a specific file. Returns count of cleared sheets."""
        with self._lock:
            if chat_id not in self._registry:
                return 0
            
            to_remove = [
                name for name, (_, m) in self._registry[chat_id].items()
                if m.file_id == file_id
            ]
            
            for name in to_remove:
                del self._registry[chat_id][name]
            
            return len(to_remove)


# Singleton instance
_registry_instance: Optional[DataFrameRegistry] = None
_instance_lock = threading.Lock()


def get_dataframe_registry() -> DataFrameRegistry:
    """Get the singleton DataFrameRegistry instance."""
    global _registry_instance
    
    if _registry_instance is None:
        with _instance_lock:
            if _registry_instance is None:
                _registry_instance = DataFrameRegistry()
    
    return _registry_instance
