"""
Export Tool - CSV/Excel File Generation

Generates downloadable files from data.
"""

from typing import Dict, Any, Optional, List
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging

from app.config import settings
from app.core import get_dataframe_registry

logger = logging.getLogger(__name__)


class ExportTool:
    """
    Tool for exporting data to downloadable files.
    
    Generates:
    - CSV files
    - Filtered/selected data exports
    - Enriched data exports
    - Data with new computed columns
    """
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.df_registry = get_dataframe_registry()
        self.export_dir = Path(settings.EXPORT_DIR)
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an export action."""
        try:
            if action == "export_csv":
                return self._export_csv(
                    params.get("sheet_name"),
                    params.get("filename"),
                    params.get("columns"),
                    params.get("add_columns"),  # New feature: add computed columns
                )
            elif action == "export_enriched":
                return self._export_enriched(params.get("filename"))
            elif action == "export_with_introduction":
                return self._export_with_introduction(
                    params.get("sheet_name"),
                    params.get("filename"),
                    params.get("limit_rows"),
                )
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            logger.exception(f"Export error: {e}")
            return {"error": str(e)}
    
    def _export_csv(
        self,
        sheet_name: Optional[str],
        filename: Optional[str],
        columns: Optional[List[str]] = None,
        add_columns: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Export a sheet to CSV."""
        # Get dataframe
        df = self.df_registry.get(self.chat_id, sheet_name)
        
        if df is None:
            sheets = self.df_registry.get_all_sheets(self.chat_id)
            if sheets:
                sheet_name = sheets[0]
                df = self.df_registry.get(self.chat_id, sheet_name)
        
        if df is None:
            return {
                "error": "No data to export",
                "available_sheets": self.df_registry.get_all_sheets(self.chat_id),
            }
        
        # Make a copy to avoid modifying original
        df_export = df.copy()
        
        # Add computed columns if specified
        if add_columns:
            for col_name, formula in add_columns.items():
                try:
                    # Safe eval for simple column operations
                    df_export[col_name] = eval(formula, {"df": df_export, "pd": pd})
                except Exception as e:
                    logger.warning(f"Could not add column {col_name}: {e}")
        
        # Select columns if specified
        if columns:
            valid_cols = [c for c in columns if c in df_export.columns]
            if valid_cols:
                df_export = df_export[valid_cols]
        
        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in (sheet_name or "export"))
            filename = f"{safe_name}_{timestamp}.csv"
        
        if not filename.endswith(".csv"):
            filename += ".csv"
        
        # Use just the filename (no chat_id prefix for cleaner URLs)
        file_path = self.export_dir / filename
        
        # Handle duplicate filenames
        counter = 1
        while file_path.exists():
            name_part = filename.rsplit(".", 1)[0]
            file_path = self.export_dir / f"{name_part}_{counter}.csv"
            counter += 1
        
        # Save file
        df_export.to_csv(file_path, index=False)
        
        logger.info(f"Exported {len(df_export)} rows to {file_path}")
        
        # Generate download URL with full backend URL
        # This ensures the link works regardless of frontend port
        download_url = f"{settings.BACKEND_URL}/exports/{file_path.name}"
        
        return {
            "success": True,
            "message": f"Successfully exported {len(df_export):,} rows to CSV",
            "filename": file_path.name,
            "rows_exported": len(df_export),
            "columns_exported": len(df_export.columns),
            "column_names": list(df_export.columns),
            "download_url": download_url,
        }
    
    def _export_with_introduction(
        self,
        sheet_name: Optional[str],
        filename: Optional[str],
        limit_rows: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Export data with an Introduction column generated from other columns."""
        df = self.df_registry.get(self.chat_id, sheet_name)
        
        if df is None:
            sheets = self.df_registry.get_all_sheets(self.chat_id)
            if sheets:
                sheet_name = sheets[0]
                df = self.df_registry.get(self.chat_id, sheet_name)
        
        if df is None:
            return {"error": "No data to export"}
        
        # Limit rows if specified
        if limit_rows and limit_rows > 0:
            df = df.head(limit_rows)
        
        df_export = df.copy()
        
        # Build introduction column based on available columns
        def build_intro(row):
            # Try to find name columns
            first_name = ""
            last_name = ""
            gender = ""
            country = ""
            age = ""
            
            for col in df_export.columns:
                col_lower = col.lower()
                val = row.get(col, "")
                if pd.isna(val):
                    val = ""
                else:
                    val = str(val)
                
                if "first" in col_lower and "name" in col_lower:
                    first_name = val
                elif "last" in col_lower and "name" in col_lower:
                    last_name = val
                elif col_lower == "name" or col_lower == "full name":
                    first_name = val
                elif "gender" in col_lower or col_lower == "sex":
                    gender = val
                elif "country" in col_lower or "nation" in col_lower:
                    country = val
                elif "age" in col_lower:
                    age = val
            
            # Build the introduction string
            name_part = f"{first_name} {last_name}".strip()
            if not name_part:
                name_part = "Unknown"
            
            intro = f"Hello, my name is {name_part}."
            
            if gender:
                intro += f" I am {gender}."
            if country:
                intro += f" I am from {country}."
            if age:
                intro += f" I am {age} years old."
            
            return intro
        
        df_export["Introduction"] = df_export.apply(build_intro, axis=1)
        
        # Generate filename
        if not filename:
            filename = "data_with_introduction"
        if not filename.endswith(".csv"):
            filename += ".csv"
        
        # Save file directly (not calling _export_csv which would refetch)
        file_path = self.export_dir / filename
        
        # Handle duplicate filenames
        counter = 1
        while file_path.exists():
            name_part = filename.rsplit(".", 1)[0]
            file_path = self.export_dir / f"{name_part}_{counter}.csv"
            counter += 1
        
        df_export.to_csv(file_path, index=False)
        
        logger.info(f"Exported {len(df_export)} rows with Introduction to {file_path}")
        
        download_url = f"{settings.BACKEND_URL}/exports/{file_path.name}"
        
        return {
            "success": True,
            "message": f"Successfully exported {len(df_export):,} rows with Introduction column to CSV",
            "filename": file_path.name,
            "rows_exported": len(df_export),
            "columns_exported": len(df_export.columns),
            "column_names": list(df_export.columns),
            "download_url": download_url,
        }
    
    def _export_enriched(self, filename: Optional[str]) -> Dict[str, Any]:
        """Export the enriched data sheet."""
        sheets = self.df_registry.get_all_sheets(self.chat_id)
        enriched_sheet = None
        
        for sheet in sheets:
            if "enriched" in sheet.lower():
                enriched_sheet = sheet
                break
        
        if not enriched_sheet:
            # If no enriched sheet, just export first sheet
            if sheets:
                return self._export_csv(sheets[0], filename)
            return {
                "error": "No data found to export",
            }
        
        return self._export_csv(enriched_sheet, filename)


def create_export_tool(chat_id: str) -> ExportTool:
    """Factory function to create an ExportTool."""
    return ExportTool(chat_id)

