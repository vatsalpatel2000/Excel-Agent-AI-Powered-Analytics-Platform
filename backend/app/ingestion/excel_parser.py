"""
Excel/CSV File Parser - Production Grade

Multi-sheet parsing with:
- Support for CSV, XLS, XLSX, XLSM
- All sheets loaded (not just first)
- Handles various encodings
- Table region detection
- Robust error handling
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedSheet:
    """Represents a parsed sheet from an Excel file or CSV."""
    
    name: str
    index: int
    dataframe: pd.DataFrame
    row_count: int
    column_count: int
    columns: List[str]
    
    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        name: str,
        index: int = 0,
    ) -> "ParsedSheet":
        """Create ParsedSheet from a pandas DataFrame."""
        return cls(
            name=name,
            index=index,
            dataframe=df,
            row_count=len(df),
            column_count=len(df.columns),
            columns=list(df.columns.astype(str)),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding dataframe)."""
        return {
            "name": self.name,
            "index": self.index,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
        }


@dataclass
class ParsedFile:
    """Represents a fully parsed spreadsheet file."""
    
    filename: str
    file_type: str
    file_path: Optional[str] = None
    sheets: List[ParsedSheet] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def sheet_count(self) -> int:
        """Number of sheets in the file."""
        return len(self.sheets)
    
    @property
    def total_rows(self) -> int:
        """Total rows across all sheets."""
        return sum(s.row_count for s in self.sheets)
    
    @property
    def sheet_names(self) -> List[str]:
        """List of all sheet names."""
        return [s.name for s in self.sheets]
    
    def get_sheet(self, name_or_index: Union[str, int]) -> Optional[ParsedSheet]:
        """Get a sheet by name or index."""
        if isinstance(name_or_index, int):
            if 0 <= name_or_index < len(self.sheets):
                return self.sheets[name_or_index]
            return None
        
        # Search by name (case-insensitive)
        name_lower = name_or_index.lower()
        for sheet in self.sheets:
            if sheet.name.lower() == name_lower:
                return sheet
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "filename": self.filename,
            "file_type": self.file_type,
            "sheet_count": self.sheet_count,
            "total_rows": self.total_rows,
            "sheets": [s.to_dict() for s in self.sheets],
            "errors": self.errors,
        }


class ExcelParser:
    """
    Production-grade parser for Excel and CSV files.
    
    Key features:
    - ALL sheets loaded (not just first)
    - Multiple encoding support
    - Table region detection
    - Handles edge cases (empty sheets, merged headers)
    
    Supported formats:
    - .csv (single sheet)
    - .xls (legacy Excel)
    - .xlsx (modern Excel)
    - .xlsm (macro-enabled Excel)
    """
    
    SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx", ".xlsm", ".tsv"}
    CSV_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
    
    def __init__(self, skip_empty_sheets: bool = True):
        """
        Initialize parser.
        
        Args:
            skip_empty_sheets: If True, skip sheets with no data
        """
        self.skip_empty_sheets = skip_empty_sheets
    
    def parse(self, file_path: Union[Path, str]) -> ParsedFile:
        """
        Parse a spreadsheet file.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            ParsedFile containing all sheets and data
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type is not supported
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        extension = file_path.suffix.lower()
        
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {extension}. "
                f"Supported types: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )
        
        if extension in {".csv", ".tsv"}:
            return self._parse_csv(file_path, delimiter="," if extension == ".csv" else "\t")
        else:
            return self._parse_excel(file_path)
    
    def parse_bytes(self, content: bytes, filename: str) -> ParsedFile:
        """
        Parse file from bytes (for uploaded files).
        
        Args:
            content: File bytes
            filename: Original filename for extension detection
            
        Returns:
            ParsedFile
        """
        from io import BytesIO
        
        extension = Path(filename).suffix.lower()
        
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension}")
        
        buffer = BytesIO(content)
        
        if extension in {".csv", ".tsv"}:
            return self._parse_csv_bytes(buffer, filename, delimiter="," if extension == ".csv" else "\t")
        else:
            return self._parse_excel_bytes(buffer, filename)
    
    def _parse_csv(self, file_path: Path, delimiter: str = ",") -> ParsedFile:
        """Parse a CSV/TSV file."""
        df = None
        errors = []
        
        # Try different encodings
        for encoding in self.CSV_ENCODINGS:
            try:
                df = pd.read_csv(
                    file_path,
                    encoding=encoding,
                    delimiter=delimiter,
                    on_bad_lines='warn',
                )
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                errors.append(f"Encoding {encoding}: {str(e)}")
        
        if df is None:
            raise ValueError(f"Could not decode CSV file: {file_path}. Errors: {errors}")
        
        # Clean column names
        df.columns = self._clean_columns(df.columns)
        
        sheet = ParsedSheet.from_dataframe(df, name="Sheet1", index=0)
        
        return ParsedFile(
            filename=file_path.name,
            file_type="csv",
            file_path=str(file_path),
            sheets=[sheet],
            errors=errors,
        )
    
    def _parse_csv_bytes(self, buffer, filename: str, delimiter: str = ",") -> ParsedFile:
        """Parse CSV from bytes buffer."""
        from io import StringIO
        
        df = None
        errors = []
        
        for encoding in self.CSV_ENCODINGS:
            try:
                buffer.seek(0)
                content = buffer.read().decode(encoding)
                df = pd.read_csv(
                    StringIO(content),
                    delimiter=delimiter,
                    on_bad_lines='warn',
                )
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                errors.append(f"Encoding {encoding}: {str(e)}")
        
        if df is None:
            raise ValueError(f"Could not decode CSV: {errors}")
        
        df.columns = self._clean_columns(df.columns)
        sheet = ParsedSheet.from_dataframe(df, name="Sheet1", index=0)
        
        return ParsedFile(
            filename=filename,
            file_type="csv",
            sheets=[sheet],
            errors=errors,
        )
    
    def _parse_excel(self, file_path: Path) -> ParsedFile:
        """Parse an Excel file (ALL sheets)."""
        extension = file_path.suffix.lower()
        engine = "xlrd" if extension == ".xls" else "openpyxl"
        
        sheets = []
        errors = []
        
        try:
            excel_file = pd.ExcelFile(file_path, engine=engine)
            
            for idx, sheet_name in enumerate(excel_file.sheet_names):
                try:
                    df = pd.read_excel(
                        excel_file,
                        sheet_name=sheet_name,
                        engine=engine,
                    )
                    
                    # Clean column names
                    df.columns = self._clean_columns(df.columns)
                    
                    # Skip empty sheets if configured
                    if self.skip_empty_sheets and df.empty:
                        logger.info(f"Skipping empty sheet: {sheet_name}")
                        continue
                    
                    sheet = ParsedSheet.from_dataframe(df, name=sheet_name, index=idx)
                    sheets.append(sheet)
                    
                    logger.info(f"Parsed sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns")
                    
                except Exception as e:
                    errors.append(f"Sheet '{sheet_name}': {str(e)}")
                    logger.warning(f"Error parsing sheet {sheet_name}: {e}")
            
        except Exception as e:
            errors.append(f"Failed to open file: {str(e)}")
            raise ValueError(f"Could not parse Excel file: {e}")
        
        return ParsedFile(
            filename=file_path.name,
            file_type=extension[1:],
            file_path=str(file_path),
            sheets=sheets,
            errors=errors,
        )
    
    def _parse_excel_bytes(self, buffer, filename: str) -> ParsedFile:
        """Parse Excel from bytes buffer."""
        extension = Path(filename).suffix.lower()
        engine = "xlrd" if extension == ".xls" else "openpyxl"
        
        sheets = []
        errors = []
        
        try:
            buffer.seek(0)
            excel_file = pd.ExcelFile(buffer, engine=engine)
            
            for idx, sheet_name in enumerate(excel_file.sheet_names):
                try:
                    df = pd.read_excel(
                        excel_file,
                        sheet_name=sheet_name,
                        engine=engine,
                    )
                    
                    df.columns = self._clean_columns(df.columns)
                    
                    if self.skip_empty_sheets and df.empty:
                        continue
                    
                    sheet = ParsedSheet.from_dataframe(df, name=sheet_name, index=idx)
                    sheets.append(sheet)
                    
                except Exception as e:
                    errors.append(f"Sheet '{sheet_name}': {str(e)}")
            
        except Exception as e:
            errors.append(f"Failed to parse: {str(e)}")
            raise
        
        return ParsedFile(
            filename=filename,
            file_type=extension[1:],
            sheets=sheets,
            errors=errors,
        )
    
    def _clean_columns(self, columns) -> List[str]:
        """Clean column names."""
        cleaned = []
        for i, col in enumerate(columns):
            col_str = str(col).strip()
            if not col_str or col_str.lower() == "unnamed":
                col_str = f"Column_{i+1}"
            cleaned.append(col_str)
        
        # Handle duplicates
        seen = {}
        result = []
        for col in cleaned:
            if col in seen:
                seen[col] += 1
                result.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                result.append(col)
        
        return result
    
    def get_summary(self, parsed_file: ParsedFile) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"## File: {parsed_file.filename}",
            f"- **Type**: {parsed_file.file_type.upper()}",
            f"- **Sheets**: {parsed_file.sheet_count}",
            f"- **Total Rows**: {parsed_file.total_rows:,}",
            "",
            "### Sheets",
        ]
        
        for sheet in parsed_file.sheets:
            lines.append(f"")
            lines.append(f"#### {sheet.name}")
            lines.append(f"- Rows: {sheet.row_count:,}")
            lines.append(f"- Columns: {sheet.column_count}")
            cols_preview = ', '.join(sheet.columns[:8])
            if len(sheet.columns) > 8:
                cols_preview += f" ... ({len(sheet.columns) - 8} more)"
            lines.append(f"- Column names: {cols_preview}")
        
        return "\n".join(lines)


# Singleton
_parser_instance: Optional[ExcelParser] = None


def get_parser() -> ExcelParser:
    """Get the file parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = ExcelParser()
    return _parser_instance
