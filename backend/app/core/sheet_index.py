"""
Sheet Index - Metadata Graph for Agent Reasoning

This provides the "map" that the LLM uses to understand what data exists.
METADATA-FIRST PROMPTING: LLM receives metadata, not raw data.

Key features:
- Rich metadata extraction for each sheet
- Natural language query parsing
- LLM context generation
- Column statistics and sample values
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import threading
import pandas as pd
import numpy as np
import re


@dataclass
class ColumnInfo:
    """Detailed information about a single column."""
    name: str
    dtype: str
    is_numeric: bool
    is_datetime: bool
    unique_count: int
    null_count: int
    total_count: int
    sample_values: List[Any]
    
    # Numeric statistics
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    std_value: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "dtype": self.dtype,
            "is_numeric": self.is_numeric,
            "is_datetime": self.is_datetime,
            "unique_count": self.unique_count,
            "null_count": self.null_count,
            "sample_values": self.sample_values[:5],
        }


@dataclass
class SheetMetadata:
    """
    Rich metadata for a single sheet.
    This is what the LLM "sees" instead of raw data.
    """
    
    file_id: str
    file_name: str
    sheet_name: str
    sheet_index: int  # 0-indexed internally
    
    # Schema
    row_count: int
    column_count: int
    columns: Dict[str, ColumnInfo] = field(default_factory=dict)
    
    # Quality flags
    has_missing_data: bool = False
    has_duplicates: bool = False
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        file_id: str,
        file_name: str,
        sheet_name: str,
        sheet_index: int,
        max_sample_values: int = 5,
    ) -> "SheetMetadata":
        """
        Create SheetMetadata from a DataFrame.
        
        This extracts all relevant information the LLM needs
        WITHOUT including the full data.
        """
        columns = {}
        
        for col in df.columns:
            series = df[col]
            is_numeric = pd.api.types.is_numeric_dtype(series)
            is_datetime = pd.api.types.is_datetime64_any_dtype(series)
            
            # Get sample values (non-null, unique)
            non_null = series.dropna()
            unique_vals = non_null.unique()[:max_sample_values]
            sample_values = [cls._make_serializable(v) for v in unique_vals]
            
            col_info = ColumnInfo(
                name=str(col),
                dtype=str(series.dtype),
                is_numeric=is_numeric,
                is_datetime=is_datetime,
                unique_count=int(series.nunique()),
                null_count=int(series.isnull().sum()),
                total_count=len(series),
                sample_values=sample_values,
            )
            
            # Add numeric statistics
            if is_numeric and len(non_null) > 0:
                try:
                    col_info.min_value = float(non_null.min())
                    col_info.max_value = float(non_null.max())
                    col_info.mean_value = float(non_null.mean())
                    col_info.std_value = float(non_null.std()) if len(non_null) > 1 else 0.0
                except (TypeError, ValueError):
                    pass
            
            columns[str(col)] = col_info
        
        return cls(
            file_id=file_id,
            file_name=file_name,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
            row_count=len(df),
            column_count=len(df.columns),
            columns=columns,
            has_missing_data=df.isnull().any().any(),
            has_duplicates=df.duplicated().any() if len(df) > 0 else False,
        )
    
    @staticmethod
    def _make_serializable(value: Any) -> Any:
        """Convert value to JSON-serializable type."""
        if pd.isna(value):
            return None
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        if hasattr(value, 'item'):
            return value.item()
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        return str(value) if not isinstance(value, (str, int, float, bool)) else value
    
    def to_llm_context(self, include_samples: bool = True) -> str:
        """
        Generate a structured context string for LLM prompts.
        This is METADATA-FIRST prompting.
        """
        lines = [
            f"### Sheet: `{self.sheet_name}` (Sheet {self.sheet_index + 1})",
            f"- **File**: {self.file_name}",
            f"- **Rows**: {self.row_count:,}",
            f"- **Columns**: {self.column_count}",
        ]
        
        if self.has_missing_data:
            lines.append("- ⚠️ Contains missing values")
        
        lines.append("")
        lines.append("**Columns:**")
        
        for col_name, col_info in self.columns.items():
            type_label = self._get_type_label(col_info)
            col_desc = f"- `{col_name}` ({type_label})"
            
            if col_info.is_numeric and col_info.min_value is not None:
                col_desc += f" [range: {col_info.min_value:,.2f} to {col_info.max_value:,.2f}]"
            elif col_info.sample_values and include_samples:
                samples = ", ".join(str(v)[:25] for v in col_info.sample_values[:3])
                col_desc += f" [e.g., {samples}]"
            
            if col_info.null_count > 0:
                null_pct = (col_info.null_count / col_info.total_count) * 100
                if null_pct > 5:
                    col_desc += f" ({null_pct:.0f}% missing)"
            
            lines.append(col_desc)
        
        return "\n".join(lines)
    
    @staticmethod
    def _get_type_label(col_info: ColumnInfo) -> str:
        """Get human-readable type label."""
        if col_info.is_numeric:
            if 'int' in col_info.dtype:
                return "integer"
            return "number"
        elif col_info.is_datetime:
            return "date/time"
        elif col_info.unique_count < 20:
            return "category"
        else:
            return "text"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "sheet_name": self.sheet_name,
            "sheet_index": self.sheet_index,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [c.to_dict() for c in self.columns.values()],
            "has_missing_data": self.has_missing_data,
        }


class SheetIndex:
    """
    Index of all sheets and their metadata for agent reasoning.
    
    This is the metadata graph the LLM uses to understand:
    - What sheets exist
    - What columns are in each sheet
    - What types of data
    - What operations are possible
    
    Key features:
    - Natural language sheet references ("sheet 2", "second sheet")
    - Cross-sheet column search
    - LLM context generation
    """
    
    # Ordinal mappings
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
        # Structure: {chat_id: {sheet_name: SheetMetadata}}
        self._index: Dict[str, Dict[str, SheetMetadata]] = {}
        self._lock = threading.RLock()
    
    def add(self, chat_id: str, metadata: SheetMetadata) -> None:
        """Add sheet metadata to the index."""
        with self._lock:
            if chat_id not in self._index:
                self._index[chat_id] = {}
            self._index[chat_id][metadata.sheet_name] = metadata
    
    def index_dataframe(
        self,
        chat_id: str,
        file_id: str,
        file_name: str,
        sheet_name: str,
        sheet_index: int,
        df: pd.DataFrame,
    ) -> SheetMetadata:
        """
        Index a DataFrame and store metadata.
        Convenience method that creates SheetMetadata and adds it.
        """
        metadata = SheetMetadata.from_dataframe(
            df=df,
            file_id=file_id,
            file_name=file_name,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
        )
        self.add(chat_id, metadata)
        return metadata
    
    def get_by_name(self, chat_id: str, sheet_name: str) -> Optional[SheetMetadata]:
        """Get sheet by exact name (case-insensitive)."""
        with self._lock:
            if chat_id not in self._index:
                return None
            
            # Exact match
            if sheet_name in self._index[chat_id]:
                return self._index[chat_id][sheet_name]
            
            # Case-insensitive match
            sheet_lower = sheet_name.lower()
            for name, metadata in self._index[chat_id].items():
                if name.lower() == sheet_lower:
                    return metadata
            
            return None
    
    def get_by_index(self, chat_id: str, sheet_index: int) -> Optional[SheetMetadata]:
        """Get sheet by 1-based index (for user convenience)."""
        with self._lock:
            if chat_id not in self._index:
                return None
            
            target = sheet_index - 1  # Convert to 0-indexed
            
            for metadata in self._index[chat_id].values():
                if metadata.sheet_index == target:
                    return metadata
            
            return None
    
    def find_by_query(self, chat_id: str, query: str) -> List[SheetMetadata]:
        """
        Find sheets matching a natural language query.
        
        Handles:
        - "sheet 2", "Sheet2", "sheet #2"
        - "second sheet", "2nd sheet"
        - "all sheets"
        - Partial name matches
        """
        with self._lock:
            if chat_id not in self._index:
                return []
            
            query_lower = query.lower().strip()
            
            # "all sheets"
            if "all sheet" in query_lower:
                return self.get_all(chat_id)
            
            matches = []
            
            # Pattern: "sheet N"
            sheet_num = re.search(r'sheet\s*#?\s*(\d+)', query_lower)
            if sheet_num:
                metadata = self.get_by_index(chat_id, int(sheet_num.group(1)))
                if metadata:
                    matches.append(metadata)
            
            # Pattern: ordinals
            for ordinal, num in self.ORDINALS.items():
                if ordinal in query_lower and "sheet" in query_lower:
                    metadata = self.get_by_index(chat_id, num)
                    if metadata and metadata not in matches:
                        matches.append(metadata)
                    break
            
            # Partial name match
            if not matches:
                for name, metadata in self._index[chat_id].items():
                    if name.lower() in query_lower or query_lower in name.lower():
                        if metadata not in matches:
                            matches.append(metadata)
            
            return sorted(matches, key=lambda m: m.sheet_index)
    
    def find_sheets_with_column(self, chat_id: str, column_name: str) -> List[SheetMetadata]:
        """Find all sheets containing a column (case-insensitive)."""
        with self._lock:
            if chat_id not in self._index:
                return []
            
            results = []
            col_lower = column_name.lower()
            
            for metadata in self._index[chat_id].values():
                for col in metadata.columns:
                    if col.lower() == col_lower:
                        results.append(metadata)
                        break
            
            return results
    
    def get_all(self, chat_id: str) -> List[SheetMetadata]:
        """Get all sheets for a chat, sorted by index."""
        with self._lock:
            if chat_id not in self._index:
                return []
            
            return sorted(
                self._index[chat_id].values(),
                key=lambda m: m.sheet_index
            )
    
    def get_sheet_names(self, chat_id: str) -> List[str]:
        """Get all sheet names, sorted by index."""
        return [m.sheet_name for m in self.get_all(chat_id)]
    
    def get_sheet_count(self, chat_id: str) -> int:
        """Get number of sheets."""
        with self._lock:
            return len(self._index.get(chat_id, {}))
    
    def build_context_for_llm(self, chat_id: str, include_samples: bool = True, max_columns: int = 15) -> str:
        """
        Build comprehensive LLM context for all sheets.
        This is the KEY to metadata-first prompting.
        
        Args:
            max_columns: Limit columns shown per sheet to reduce tokens
        """
        sheets = self.get_all(chat_id)
        
        if not sheets:
            return "No data files are currently loaded."
        
        total_rows = sum(s.row_count for s in sheets)
        
        lines = [
            "## Available Data",
            "",
            f"**Total**: {len(sheets)} sheet(s), {total_rows:,} rows",
            "",
            "### Sheet Overview",
            "| # | Sheet Name | Rows | Columns |",
            "|---|------------|------|---------|",
        ]
        
        for m in sheets:
            lines.append(f"| {m.sheet_index + 1} | {m.sheet_name} | {m.row_count:,} | {m.column_count} |")
        
        lines.append("")
        
        # Detailed info per sheet (with column limit)
        for metadata in sheets:
            lines.append(self._build_sheet_context(metadata, include_samples, max_columns))
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_sheet_context(self, metadata: SheetMetadata, include_samples: bool = True, max_columns: int = 15) -> str:
        """Build context for a single sheet with column limit."""
        lines = [
            f"### Sheet: `{metadata.sheet_name}` (Sheet {metadata.sheet_index + 1})",
            f"- **File**: {metadata.file_name}",
            f"- **Rows**: {metadata.row_count:,}",
            f"- **Columns**: {metadata.column_count}",
        ]
        
        if metadata.has_missing_data:
            lines.append("- ⚠️ Contains missing values")
        
        lines.append("")
        lines.append("**Columns:**")
        
        col_items = list(metadata.columns.items())
        
        for col_name, col_info in col_items[:max_columns]:
            type_label = metadata._get_type_label(col_info)
            col_desc = f"- `{col_name}` ({type_label})"
            
            if col_info.is_numeric and col_info.min_value is not None:
                col_desc += f" [range: {col_info.min_value:,.0f} to {col_info.max_value:,.0f}]"
            elif col_info.sample_values and include_samples:
                samples = ", ".join(str(v)[:20] for v in col_info.sample_values[:2])
                col_desc += f" [e.g., {samples}]"
            
            lines.append(col_desc)
        
        if len(col_items) > max_columns:
            lines.append(f"- ... and {len(col_items) - max_columns} more columns")
        
        return "\n".join(lines)
    
    def build_compact_context(self, chat_id: str) -> str:
        """
        Build a very compact context for token-constrained scenarios.
        Shows only essential info.
        """
        sheets = self.get_all(chat_id)
        
        if not sheets:
            return "No data loaded."
        
        lines = [f"Data: {len(sheets)} sheet(s), {sum(s.row_count for s in sheets):,} rows"]
        
        for m in sheets:
            cols = list(m.columns.keys())[:8]
            cols_str = ", ".join(cols)
            if len(m.columns) > 8:
                cols_str += f" (+{len(m.columns) - 8} more)"
            lines.append(f"- {m.sheet_name}: {m.row_count:,} rows [{cols_str}]")
        
        return "\n".join(lines)
    
    def to_llm_context(self, chat_id: str, include_samples: bool = True) -> str:
        """Alias for build_context_for_llm for compatibility."""
        return self.build_context_for_llm(chat_id, include_samples)
    
    def clear_chat(self, chat_id: str) -> int:
        """Clear all sheets for a chat."""
        with self._lock:
            if chat_id not in self._index:
                return 0
            count = len(self._index[chat_id])
            del self._index[chat_id]
            return count


# Singleton instance
_sheet_index: Optional[SheetIndex] = None
_index_lock = threading.Lock()


def get_sheet_index() -> SheetIndex:
    """Get the singleton SheetIndex instance."""
    global _sheet_index
    
    if _sheet_index is None:
        with _index_lock:
            if _sheet_index is None:
                _sheet_index = SheetIndex()
    
    return _sheet_index
