"""
Schema Normalizer - Clean and Standardize DataFrame Schemas

Features:
- Header cleaning (whitespace, special chars)
- Type inference and optimization
- Duplicate column name resolution
- Missing value handling
"""

from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
import re
import logging

logger = logging.getLogger(__name__)


class SchemaNormalizer:
    """
    Normalizes DataFrame schemas for consistent processing.
    
    Key features:
    - Clean column names
    - Infer optimal data types
    - Handle duplicates
    - Standardize missing values
    """
    
    # Common date formats to try
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    
    def __init__(
        self,
        clean_headers: bool = True,
        infer_types: bool = True,
        handle_duplicates: bool = True,
    ):
        self.clean_headers = clean_headers
        self.infer_types = infer_types
        self.handle_duplicates = handle_duplicates
    
    def normalize(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Normalize a DataFrame.
        
        Returns:
            (normalized_df, changes_dict)
        """
        changes = {
            "columns_renamed": {},
            "types_changed": {},
            "duplicates_resolved": [],
        }
        
        result = df.copy()
        
        if self.clean_headers:
            result, renamed = self._clean_column_names(result)
            changes["columns_renamed"] = renamed
        
        if self.handle_duplicates:
            result, dups = self._resolve_duplicates(result)
            changes["duplicates_resolved"] = dups
        
        if self.infer_types:
            result, type_changes = self._infer_types(result)
            changes["types_changed"] = type_changes
        
        return result, changes
    
    def _clean_column_names(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Clean column names."""
        renamed = {}
        new_columns = []
        
        for col in df.columns:
            original = str(col)
            cleaned = self._clean_single_name(original)
            
            if cleaned != original:
                renamed[original] = cleaned
            
            new_columns.append(cleaned)
        
        df.columns = new_columns
        return df, renamed
    
    def _clean_single_name(self, name: str) -> str:
        """Clean a single column name."""
        # Strip whitespace
        name = str(name).strip()
        
        # Handle empty/unnamed
        if not name or name.lower().startswith("unnamed"):
            return name  # Will be handled by duplicate resolution
        
        # Replace newlines and tabs
        name = re.sub(r'[\n\r\t]+', ' ', name)
        
        # Collapse multiple spaces
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def _resolve_duplicates(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Resolve duplicate column names."""
        duplicates = []
        seen = {}
        new_columns = []
        
        for col in df.columns:
            col_str = str(col)
            
            # Handle empty columns
            if not col_str or col_str.lower().startswith("unnamed"):
                col_str = "Column"
            
            if col_str in seen:
                seen[col_str] += 1
                new_name = f"{col_str}_{seen[col_str]}"
                duplicates.append(f"{col_str} -> {new_name}")
                new_columns.append(new_name)
            else:
                seen[col_str] = 0
                new_columns.append(col_str)
        
        df.columns = new_columns
        return df, duplicates
    
    def _infer_types(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Infer and convert to optimal data types."""
        type_changes = {}
        
        for col in df.columns:
            original_dtype = str(df[col].dtype)
            
            # Skip if already optimal
            if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
                continue
            
            # Try numeric conversion
            if df[col].dtype == object:
                numeric_result = self._try_numeric(df[col])
                if numeric_result is not None:
                    df[col] = numeric_result
                    type_changes[col] = f"{original_dtype} -> {df[col].dtype}"
                    continue
                
                # Try date conversion
                date_result = self._try_date(df[col])
                if date_result is not None:
                    df[col] = date_result
                    type_changes[col] = f"{original_dtype} -> datetime64"
                    continue
                
                # Try category for low cardinality
                if df[col].nunique() / len(df) < 0.5 and df[col].nunique() < 100:
                    df[col] = df[col].astype('category')
                    type_changes[col] = f"{original_dtype} -> category"
        
        return df, type_changes
    
    def _try_numeric(self, series: pd.Series) -> Optional[pd.Series]:
        """Try to convert series to numeric."""
        try:
            # Remove common non-numeric chars
            cleaned = series.astype(str).str.replace(r'[$,€£%]', '', regex=True)
            cleaned = cleaned.str.strip()
            
            # Try conversion
            numeric = pd.to_numeric(cleaned, errors='coerce')
            
            # Only convert if >80% successful
            non_null_original = series.notna().sum()
            non_null_numeric = numeric.notna().sum()
            
            if non_null_original > 0 and non_null_numeric / non_null_original > 0.8:
                return numeric
            
        except Exception:
            pass
        
        return None
    
    def _try_date(self, series: pd.Series) -> Optional[pd.Series]:
        """Try to convert series to datetime."""
        try:
            # First try automatic parsing (without deprecated parameter)
            dates = pd.to_datetime(series, errors='coerce')
            
            non_null_original = series.notna().sum()
            non_null_dates = dates.notna().sum()
            
            if non_null_original > 0 and non_null_dates / non_null_original > 0.8:
                return dates
            
            # Try explicit formats
            for fmt in self.DATE_FORMATS:
                try:
                    dates = pd.to_datetime(series, format=fmt, errors='coerce')
                    if dates.notna().sum() / non_null_original > 0.8:
                        return dates
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return None
    
    def get_column_summary(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Get a summary of all columns."""
        summary = []
        
        for col in df.columns:
            series = df[col]
            info = {
                "name": col,
                "dtype": str(series.dtype),
                "non_null_count": int(series.notna().sum()),
                "null_count": int(series.isna().sum()),
                "unique_count": int(series.nunique()),
            }
            
            if pd.api.types.is_numeric_dtype(series):
                info["min"] = float(series.min()) if series.notna().any() else None
                info["max"] = float(series.max()) if series.notna().any() else None
                info["mean"] = float(series.mean()) if series.notna().any() else None
            
            summary.append(info)
        
        return summary


# Singleton
_normalizer_instance: Optional[SchemaNormalizer] = None


def get_normalizer() -> SchemaNormalizer:
    """Get the schema normalizer instance."""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = SchemaNormalizer()
    return _normalizer_instance
