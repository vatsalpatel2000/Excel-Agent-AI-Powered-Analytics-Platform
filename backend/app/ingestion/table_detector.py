"""
Table Detector - ML-Assisted Table Region Detection

Detects table boundaries within sheets using:
- Row entropy analysis
- Empty row/column gap detection
- Header row detection
- Data type transition detection
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class TableRegion:
    """Represents a detected table region within a sheet."""
    start_row: int
    end_row: int
    start_col: int
    end_col: int
    row_count: int
    col_count: int
    has_header: bool
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_row": self.start_row,
            "end_row": self.end_row,
            "start_col": self.start_col,
            "end_col": self.end_col,
            "row_count": self.row_count,
            "col_count": self.col_count,
            "has_header": self.has_header,
            "confidence": self.confidence,
        }


class TableDetector:
    """
    Detects table regions within spreadsheet data.
    
    Useful for:
    - Sheets with multiple tables
    - Data with header rows not on row 1
    - Mixed content sheets (text + tables)
    
    Uses heuristics:
    - Empty row detection (gap between tables)
    - Type consistency within columns
    - Header row patterns
    """
    
    def __init__(
        self,
        min_rows: int = 2,
        min_cols: int = 2,
        empty_threshold: float = 0.8,
    ):
        """
        Initialize detector.
        
        Args:
            min_rows: Minimum rows for a valid table
            min_cols: Minimum columns for a valid table
            empty_threshold: Ratio of empty cells to consider row/col empty
        """
        self.min_rows = min_rows
        self.min_cols = min_cols
        self.empty_threshold = empty_threshold
    
    def detect_tables(self, df: pd.DataFrame) -> List[TableRegion]:
        """
        Detect all table regions in a DataFrame.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            List of detected TableRegion objects
        """
        if df.empty:
            return []
        
        # Find row regions (separated by empty rows)
        row_regions = self._find_row_regions(df)
        
        tables = []
        for start_row, end_row in row_regions:
            # Extract sub-dataframe
            sub_df = df.iloc[start_row:end_row + 1]
            
            # Find column regions (separated by empty columns)
            col_regions = self._find_col_regions(sub_df)
            
            for start_col, end_col in col_regions:
                row_count = end_row - start_row + 1
                col_count = end_col - start_col + 1
                
                if row_count >= self.min_rows and col_count >= self.min_cols:
                    has_header = self._detect_header(df, start_row, start_col, end_col)
                    confidence = self._calculate_confidence(
                        df, start_row, end_row, start_col, end_col
                    )
                    
                    tables.append(TableRegion(
                        start_row=start_row,
                        end_row=end_row,
                        start_col=start_col,
                        end_col=end_col,
                        row_count=row_count,
                        col_count=col_count,
                        has_header=has_header,
                        confidence=confidence,
                    ))
        
        return tables
    
    def _find_row_regions(self, df: pd.DataFrame) -> List[Tuple[int, int]]:
        """Find contiguous non-empty row regions."""
        regions = []
        in_region = False
        start = 0
        
        for idx in range(len(df)):
            row = df.iloc[idx]
            is_empty = self._is_row_empty(row)
            
            if not is_empty and not in_region:
                # Start new region
                start = idx
                in_region = True
            elif is_empty and in_region:
                # End current region
                regions.append((start, idx - 1))
                in_region = False
        
        # Handle final region
        if in_region:
            regions.append((start, len(df) - 1))
        
        return regions
    
    def _find_col_regions(self, df: pd.DataFrame) -> List[Tuple[int, int]]:
        """Find contiguous non-empty column regions."""
        regions = []
        in_region = False
        start = 0
        
        for idx in range(len(df.columns)):
            col = df.iloc[:, idx]
            is_empty = self._is_col_empty(col)
            
            if not is_empty and not in_region:
                start = idx
                in_region = True
            elif is_empty and in_region:
                regions.append((start, idx - 1))
                in_region = False
        
        if in_region:
            regions.append((start, len(df.columns) - 1))
        
        return regions if regions else [(0, len(df.columns) - 1)]
    
    def _is_row_empty(self, row: pd.Series) -> bool:
        """Check if a row is mostly empty."""
        empty_count = row.isna().sum() + (row.astype(str).str.strip() == '').sum()
        return empty_count / len(row) >= self.empty_threshold
    
    def _is_col_empty(self, col: pd.Series) -> bool:
        """Check if a column is mostly empty."""
        empty_count = col.isna().sum() + (col.astype(str).str.strip() == '').sum()
        return empty_count / len(col) >= self.empty_threshold
    
    def _detect_header(
        self,
        df: pd.DataFrame,
        start_row: int,
        start_col: int,
        end_col: int,
    ) -> bool:
        """Detect if the first row of a region is a header."""
        if start_row >= len(df):
            return False
        
        first_row = df.iloc[start_row, start_col:end_col + 1]
        
        # Check if all values are strings (header-like)
        all_strings = all(
            isinstance(v, str) or pd.isna(v)
            for v in first_row
        )
        
        if not all_strings:
            return False
        
        # Check if second row has different types
        if start_row + 1 < len(df):
            second_row = df.iloc[start_row + 1, start_col:end_col + 1]
            has_numeric = any(
                pd.api.types.is_numeric_dtype(type(v)) or isinstance(v, (int, float))
                for v in second_row if pd.notna(v)
            )
            if has_numeric:
                return True
        
        # Check for typical header patterns
        header_patterns = ['id', 'name', 'date', 'no', 's.no', 'description', 'value', 'amount']
        for val in first_row:
            if pd.notna(val) and str(val).lower().strip() in header_patterns:
                return True
        
        return False
    
    def _calculate_confidence(
        self,
        df: pd.DataFrame,
        start_row: int,
        end_row: int,
        start_col: int,
        end_col: int,
    ) -> float:
        """Calculate confidence score for detected table."""
        scores = []
        
        region = df.iloc[start_row:end_row + 1, start_col:end_col + 1]
        
        # Score based on data density
        total_cells = region.size
        non_empty = region.notna().sum().sum()
        density_score = non_empty / total_cells if total_cells > 0 else 0
        scores.append(density_score)
        
        # Score based on type consistency per column
        type_scores = []
        for col_idx in range(region.shape[1]):
            col = region.iloc[:, col_idx]
            non_null = col.dropna()
            if len(non_null) > 0:
                types = non_null.apply(lambda x: type(x).__name__).value_counts()
                dominant = types.iloc[0] / len(non_null) if len(types) > 0 else 0
                type_scores.append(dominant)
        
        if type_scores:
            scores.append(np.mean(type_scores))
        
        # Score based on size
        size_score = min(1.0, (end_row - start_row) / 10) * min(1.0, (end_col - start_col) / 5)
        scores.append(size_score)
        
        return float(np.mean(scores)) if scores else 0.5
    
    def extract_table(
        self,
        df: pd.DataFrame,
        region: TableRegion,
    ) -> pd.DataFrame:
        """Extract a table region as a new DataFrame."""
        extracted = df.iloc[
            region.start_row:region.end_row + 1,
            region.start_col:region.end_col + 1
        ].copy()
        
        # If header detected, use first row as column names
        if region.has_header and len(extracted) > 1:
            extracted.columns = extracted.iloc[0].astype(str).tolist()
            extracted = extracted.iloc[1:].reset_index(drop=True)
        
        return extracted


# Singleton
_detector_instance: Optional[TableDetector] = None


def get_table_detector() -> TableDetector:
    """Get the table detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = TableDetector()
    return _detector_instance
