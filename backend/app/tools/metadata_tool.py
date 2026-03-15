"""
Metadata Tool - Sheet/Column Discovery

Provides metadata about available data for agent reasoning.
This is the first tool agents should use to understand what data exists.
"""

from typing import Dict, List, Any, Optional
from app.core import get_dataframe_registry, get_sheet_index


class MetadataTool:
    """
    Tool for querying metadata about available data.
    
    Actions:
    - list_sheets: List all available sheets
    - get_sheet_info: Get detailed info about a sheet
    - get_column_stats: Get statistics for a column
    - get_sample_rows: Get sample rows from a sheet
    - search_columns: Search for columns across sheets
    """
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.df_registry = get_dataframe_registry()
        self.sheet_index = get_sheet_index()
    
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a metadata action."""
        if action == "list_sheets":
            return self._list_sheets()
        elif action == "get_sheet_info":
            return self._get_sheet_info(params.get("sheet_name"))
        elif action == "get_column_stats":
            return self._get_column_stats(
                params.get("sheet_name"),
                params.get("column_name"),
            )
        elif action == "get_sample_rows":
            return self._get_sample_rows(
                params.get("sheet_name"),
                params.get("n", 5),
            )
        elif action == "search_columns":
            return self._search_columns(params.get("column_name", ""))
        else:
            return {"error": f"Unknown action: {action}"}
    
    def _list_sheets(self) -> Dict[str, Any]:
        """List all available sheets with basic info."""
        sheets = self.sheet_index.get_all(self.chat_id)
        
        if not sheets:
            return {
                "success": True,
                "sheets": [],
                "message": "No sheets loaded",
            }
        
        sheet_list = []
        for s in sheets:
            sheet_list.append({
                "name": s.sheet_name,
                "index": s.sheet_index + 1,  # 1-indexed for users
                "rows": s.row_count,
                "columns": list(s.columns.keys()),
                "has_missing": s.has_missing_data,
            })
        
        return {
            "success": True,
            "total_sheets": len(sheets),
            "total_rows": sum(s.row_count for s in sheets),
            "sheets": sheet_list,
        }
    
    def _get_sheet_info(self, sheet_name: Optional[str]) -> Dict[str, Any]:
        """Get detailed info about a specific sheet."""
        if not sheet_name:
            sheets = self.sheet_index.get_all(self.chat_id)
            if sheets:
                sheet_name = sheets[0].sheet_name
            else:
                return {"error": "No sheets available"}
        
        metadata = self.sheet_index.get_by_name(self.chat_id, sheet_name)
        
        if not metadata:
            # Try by index
            matched = self.sheet_index.find_by_query(self.chat_id, sheet_name)
            if matched:
                metadata = matched[0]
            else:
                available = self.sheet_index.get_sheet_names(self.chat_id)
                return {
                    "error": f"Sheet '{sheet_name}' not found",
                    "available_sheets": available,
                }
        
        columns_info = []
        for col_name, col_info in metadata.columns.items():
            info = {
                "name": col_name,
                "type": col_info.dtype,
                "unique_values": col_info.unique_count,
                "missing_values": col_info.null_count,
                "sample_values": col_info.sample_values[:3],
            }
            if col_info.is_numeric:
                info["min"] = col_info.min_value
                info["max"] = col_info.max_value
                info["mean"] = col_info.mean_value
            columns_info.append(info)
        
        return {
            "success": True,
            "sheet_name": metadata.sheet_name,
            "rows": metadata.row_count,
            "columns": columns_info,
            "has_missing_data": metadata.has_missing_data,
        }
    
    def _get_column_stats(
        self,
        sheet_name: Optional[str],
        column_name: Optional[str],
    ) -> Dict[str, Any]:
        """Get detailed statistics for a column."""
        if not column_name:
            return {"error": "column_name is required"}
        
        # Get the sheet
        if not sheet_name:
            sheets = self.sheet_index.get_all(self.chat_id)
            if sheets:
                sheet_name = sheets[0].sheet_name
            else:
                return {"error": "No sheets available"}
        
        df = self.df_registry.get(self.chat_id, sheet_name)
        if df is None:
            return {"error": f"Sheet '{sheet_name}' not found"}
        
        # Find column (case-insensitive)
        actual_col = None
        col_lower = column_name.lower()
        for col in df.columns:
            if col.lower() == col_lower:
                actual_col = col
                break
        
        if actual_col is None:
            return {
                "error": f"Column '{column_name}' not found",
                "available_columns": list(df.columns),
            }
        
        series = df[actual_col]
        
        stats = {
            "column_name": actual_col,
            "data_type": str(series.dtype),
            "total_count": len(series),
            "non_null_count": int(series.notna().sum()),
            "null_count": int(series.isna().sum()),
            "unique_count": int(series.nunique()),
        }
        
        if series.dtype in ['int64', 'float64', 'int32', 'float32']:
            stats.update({
                "min": float(series.min()) if series.notna().any() else None,
                "max": float(series.max()) if series.notna().any() else None,
                "mean": float(series.mean()) if series.notna().any() else None,
                "median": float(series.median()) if series.notna().any() else None,
                "std": float(series.std()) if series.notna().any() else None,
            })
        else:
            # Top values for categorical
            top_values = series.value_counts().head(10)
            stats["top_values"] = {str(k): int(v) for k, v in top_values.items()}
        
        return {"success": True, **stats}
    
    def _get_sample_rows(
        self,
        sheet_name: Optional[str],
        n: int = 5,
    ) -> Dict[str, Any]:
        """Get sample rows from a sheet."""
        if not sheet_name:
            sheets = self.sheet_index.get_all(self.chat_id)
            if sheets:
                sheet_name = sheets[0].sheet_name
            else:
                return {"error": "No sheets available"}
        
        df = self.df_registry.get(self.chat_id, sheet_name)
        if df is None:
            matched = self.sheet_index.find_by_query(self.chat_id, sheet_name)
            if matched:
                df = self.df_registry.get(self.chat_id, matched[0].sheet_name)
        
        if df is None:
            return {"error": f"Sheet '{sheet_name}' not found"}
        
        # Get sample rows
        sample = df.head(min(n, len(df)))
        
        rows = []
        for _, row in sample.iterrows():
            row_dict = {}
            for col in sample.columns:
                val = row[col]
                # Convert to JSON-serializable
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                elif hasattr(val, 'item'):
                    val = val.item()
                elif isinstance(val, float) and (val != val):  # NaN check
                    val = None
                row_dict[col] = val
            rows.append(row_dict)
        
        return {
            "success": True,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "sample_count": len(rows),
            "columns": list(df.columns),
            "rows": rows,
        }
    
    def _search_columns(self, query: str) -> Dict[str, Any]:
        """Search for columns matching a query across all sheets."""
        if not query:
            return {"error": "Search query is required"}
        
        query_lower = query.lower()
        results = []
        
        for sheet in self.sheet_index.get_all(self.chat_id):
            for col_name, col_info in sheet.columns.items():
                if query_lower in col_name.lower():
                    results.append({
                        "sheet_name": sheet.sheet_name,
                        "column_name": col_name,
                        "type": col_info.dtype,
                        "unique_count": col_info.unique_count,
                    })
        
        return {
            "success": True,
            "query": query,
            "matches": len(results),
            "columns": results,
        }


def create_metadata_tool(chat_id: str) -> MetadataTool:
    """Factory function to create a MetadataTool."""
    return MetadataTool(chat_id)
