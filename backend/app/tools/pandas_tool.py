"""
Pandas Tool - Deterministic Data Operations

All calculations and data operations go through this tool.
The LLM NEVER performs calculations directly.
"""

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
import logging

from app.core import get_dataframe_registry, get_sheet_index, get_execution_guard

logger = logging.getLogger(__name__)


class PandasTool:
    """
    Tool for executing data operations via Pandas - Production Grade.
    
    All operations are deterministic and verified.
    Results are returned in a format suitable for LLM synthesis.
    
    Operations:
    - filter: Filter rows by conditions
    - select: Select specific columns
    - groupby: Group and aggregate
    - sort: Sort by columns
    - describe: Statistical summary
    - value_counts: Count unique values
    - head/tail: Get first/last N rows
    - count/sum/mean: Simple aggregations
    - unique: Get unique values
    - query: Run a pandas query expression
    - code: Execute custom pandas code
    - crosstab: Cross-tabulation for categorical analysis
    - percentile: Calculate specific percentiles
    - pivot_table: Create pivot tables
    - correlation: Quick correlation between columns
    - rolling: Rolling window calculations
    """
    
    MAX_RESULT_ROWS = 5000  # Production-grade result capacity
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.df_registry = get_dataframe_registry()
        self.sheet_index = get_sheet_index()
        self.execution_guard = get_execution_guard()
    
    def execute(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a pandas operation."""
        # Get the target dataframe
        sheet_name = params.get("sheet_name")
        df = self._get_dataframe(sheet_name)
        
        if df is None:
            available = self.df_registry.get_all_sheets(self.chat_id)
            return {
                "error": f"Sheet not found: {sheet_name}",
                "available_sheets": available,
            }
        
        # Route to appropriate operation
        if operation == "filter":
            return self._filter(df, params)
        elif operation == "select":
            return self._select(df, params)
        elif operation == "groupby":
            return self._groupby(df, params)
        elif operation == "sort":
            return self._sort(df, params)
        elif operation == "describe":
            return self._describe(df)
        elif operation == "value_counts":
            return self._value_counts(df, params)
        elif operation == "head":
            return self._head(df, params)
        elif operation == "tail":
            return self._tail(df, params)
        elif operation == "count":
            return self._count(df, params)
        elif operation == "sum":
            return self._aggregate(df, params, "sum")
        elif operation == "mean":
            return self._aggregate(df, params, "mean")
        elif operation == "unique":
            return self._unique(df, params)
        elif operation == "query":
            return self._query(df, params)
        elif operation == "code":
            return self._execute_code(params)
        elif operation == "crosstab":
            return self._crosstab(df, params)
        elif operation == "percentile":
            return self._percentile(df, params)
        elif operation == "pivot_table":
            return self._pivot_table(df, params)
        elif operation == "correlation":
            return self._correlation(df, params)
        elif operation == "rolling":
            return self._rolling(df, params)
        else:
            return {"error": f"Unknown operation: {operation}", "available_operations": [
                "filter", "select", "groupby", "sort", "describe", "value_counts",
                "head", "tail", "count", "sum", "mean", "unique", "query", "code",
                "crosstab", "percentile", "pivot_table", "correlation", "rolling"
            ]}
    
    def _get_dataframe(self, sheet_name: Optional[str]) -> Optional[pd.DataFrame]:
        """Get DataFrame by name or return first sheet."""
        if sheet_name:
            # Try exact match first
            df = self.df_registry.get(self.chat_id, sheet_name)
            if df is not None:
                return df
            
            # Try query match (handles "sheet 2", etc.)
            df = self.df_registry.get_by_query(self.chat_id, sheet_name)
            if df is not None:
                return df
        
        # Return first sheet if no name specified
        sheets = self.df_registry.get_all_sheets(self.chat_id)
        if sheets:
            return self.df_registry.get(self.chat_id, sheets[0])
        
        return None
    
    def _format_result(
        self,
        data: Any,
        result_type: str = "data",
        truncated: bool = False,
    ) -> Dict[str, Any]:
        """Format result for LLM consumption."""
        if isinstance(data, pd.DataFrame):
            # Convert to serializable format
            rows = min(len(data), self.MAX_RESULT_ROWS)
            sample = data.head(rows)
            
            return {
                "success": True,
                "result_type": "table",
                "total_rows": len(data),
                "shown_rows": rows,
                "columns": list(data.columns),
                "data": self._df_to_records(sample),
                "truncated": len(data) > rows,
            }
        elif isinstance(data, pd.Series):
            return {
                "success": True,
                "result_type": "series",
                "name": str(data.name) if data.name else "result",
                "length": len(data),
                "data": self._series_to_dict(data.head(100)),
            }
        elif isinstance(data, (int, float, np.integer, np.floating)):
            return {
                "success": True,
                "result_type": "number",
                "value": float(data) if pd.notna(data) else None,
            }
        elif isinstance(data, list):
            return {
                "success": True,
                "result_type": "list",
                "length": len(data),
                "data": data[:100],
                "truncated": len(data) > 100,
            }
        else:
            return {
                "success": True,
                "result_type": type(data).__name__,
                "value": str(data)[:1000],
            }
    
    def _df_to_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Convert DataFrame to list of dicts with proper serialization."""
        records = []
        for _, row in df.iterrows():
            record = {}
            for col in df.columns:
                val = row[col]
                record[str(col)] = self._serialize_value(val)
            records.append(record)
        return records
    
    def _series_to_dict(self, series: pd.Series) -> Dict[str, Any]:
        """Convert Series to dict with proper serialization."""
        return {
            str(k): self._serialize_value(v)
            for k, v in series.items()
        }
    
    def _serialize_value(self, val: Any) -> Any:
        """Convert a value to JSON-serializable format."""
        if pd.isna(val):
            return None
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        if isinstance(val, (np.integer, np.floating)):
            return val.item()
        if isinstance(val, np.bool_):
            return bool(val)
        if isinstance(val, (list, dict)):
            return val
        if isinstance(val, (str, int, float, bool)):
            return val
        return str(val)
    
    def _filter(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Filter rows by conditions."""
        conditions = params.get("conditions", [])
        
        if not conditions:
            return {"error": "No filter conditions provided"}
        
        result = df.copy()
        
        for cond in conditions:
            col = cond.get("column")
            op = cond.get("operator", "==")
            val = cond.get("value")
            
            if col not in result.columns:
                # Try case-insensitive match
                matched = None
                for c in result.columns:
                    if c.lower() == col.lower():
                        matched = c
                        break
                if not matched:
                    return {
                        "error": f"Column '{col}' not found",
                        "available_columns": list(result.columns),
                    }
                col = matched
            
            try:
                if op == "==":
                    result = result[result[col] == val]
                elif op == "!=":
                    result = result[result[col] != val]
                elif op == ">":
                    result = result[result[col] > val]
                elif op == ">=":
                    result = result[result[col] >= val]
                elif op == "<":
                    result = result[result[col] < val]
                elif op == "<=":
                    result = result[result[col] <= val]
                elif op == "contains":
                    result = result[result[col].astype(str).str.contains(str(val), case=False, na=False)]
                elif op == "isnull":
                    result = result[result[col].isnull()]
                elif op == "notnull":
                    result = result[result[col].notnull()]
            except Exception as e:
                return {"error": f"Filter error on {col}: {str(e)}"}
        
        return self._format_result(result)
    
    def _select(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Select specific columns."""
        columns = params.get("columns", [])
        
        if not columns:
            return {"error": "No columns specified"}
        
        valid_cols = []
        for col in columns:
            if col in df.columns:
                valid_cols.append(col)
            else:
                # Case-insensitive match
                for c in df.columns:
                    if c.lower() == col.lower():
                        valid_cols.append(c)
                        break
        
        if not valid_cols:
            return {
                "error": "No valid columns found",
                "requested": columns,
                "available": list(df.columns),
            }
        
        return self._format_result(df[valid_cols])
    
    def _groupby(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Group by columns and aggregate."""
        group_by = params.get("group_by", [])
        aggregations = params.get("aggregations", {})
        
        if not group_by:
            return {"error": "No group_by columns specified"}
        
        valid_group = [c for c in group_by if c in df.columns]
        if not valid_group:
            return {
                "error": "Invalid group_by columns",
                "available": list(df.columns),
            }
        
        try:
            if aggregations:
                valid_aggs = {}
                for col, agg in aggregations.items():
                    if col in df.columns:
                        valid_aggs[col] = agg
                
                if not valid_aggs:
                    # Default to count if no valid aggregations
                    result = df.groupby(valid_group).size().reset_index(name='count')
                else:
                    result = df.groupby(valid_group).agg(valid_aggs).reset_index()
            else:
                result = df.groupby(valid_group).size().reset_index(name='count')
            
            return self._format_result(result)
        except Exception as e:
            return {"error": f"Groupby error: {str(e)}"}
    
    def _sort(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sort by columns."""
        by = params.get("by", params.get("columns", []))
        ascending = params.get("ascending", True)
        
        if not by:
            return {"error": "No sort column specified"}
        
        valid = [c for c in by if c in df.columns]
        if not valid:
            return {"error": "Invalid sort columns", "available": list(df.columns)}
        
        result = df.sort_values(by=valid, ascending=ascending)
        return self._format_result(result)
    
    def _describe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Statistical summary."""
        desc = df.describe(include='all')
        return self._format_result(desc.T)  # Transpose for readability
    
    def _value_counts(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Count unique values in a column."""
        column = params.get("column")
        top_n = params.get("top_n", 20)
        
        if not column:
            return {"error": "No column specified"}
        
        if column not in df.columns:
            return {"error": f"Column '{column}' not found", "available": list(df.columns)}
        
        counts = df[column].value_counts().head(top_n)
        return self._format_result(counts)
    
    def _head(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get first N rows."""
        n = params.get("n", 10)
        return self._format_result(df.head(n))
    
    def _tail(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get last N rows."""
        n = params.get("n", 10)
        return self._format_result(df.tail(n))
    
    def _count(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Count rows or column non-null values."""
        column = params.get("column")
        
        if column:
            if column not in df.columns:
                return {"error": f"Column '{column}' not found"}
            count = int(df[column].notna().sum())
            return {"success": True, "result_type": "number", "value": count, "description": f"Non-null count for {column}"}
        
        return {"success": True, "result_type": "number", "value": len(df), "description": "Total row count"}
    
    def _aggregate(self, df: pd.DataFrame, params: Dict[str, Any], agg_type: str) -> Dict[str, Any]:
        """Perform aggregation (sum/mean) on a column."""
        column = params.get("column")
        
        # Get all numeric columns for helpful error messages
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not column:
            return {
                "error": "No column specified for aggregation",
                "available_numeric_columns": numeric_cols,
                "hint": f"Please specify which column to {agg_type}. Available numeric columns: {numeric_cols}",
                "action_required": "ASK_USER_FOR_COLUMN"
            }
        
        # Try case-insensitive column matching
        matched_column = self._match_column(df, column)
        
        if not matched_column:
            return {
                "error": f"Column '{column}' not found",
                "available_columns": list(df.columns),
                "numeric_columns": numeric_cols,
                "hint": f"Did you mean one of these numeric columns? {numeric_cols}",
                "action_required": "ASK_USER_FOR_COLUMN"
            }
        
        # Check if matched column is numeric
        if matched_column not in numeric_cols:
            return {
                "error": f"Column '{matched_column}' is not numeric (type: {df[matched_column].dtype})",
                "available_numeric_columns": numeric_cols,
                "hint": f"For {agg_type}, please use a numeric column. Available: {numeric_cols}",
                "action_required": "ASK_USER_FOR_COLUMN"
            }
        
        try:
            if agg_type == "sum":
                value = float(df[matched_column].sum())
            elif agg_type == "mean":
                value = float(df[matched_column].mean())
            else:
                return {"error": f"Unknown aggregation: {agg_type}"}
            
            return {
                "success": True,
                "result_type": "number",
                "value": value,
                "operation": agg_type,
                "column": matched_column,
            }
        except Exception as e:
            return {"error": f"{agg_type} error on {matched_column}: {str(e)}"}
    
    def _unique(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get unique values from a column."""
        column = params.get("column")
        
        if not column:
            return {"error": "No column specified"}
        
        if column not in df.columns:
            return {"error": f"Column '{column}' not found"}
        
        unique_vals = df[column].dropna().unique().tolist()
        return {
            "success": True,
            "result_type": "list",
            "column": column,
            "unique_count": len(unique_vals),
            "data": unique_vals[:100],
            "truncated": len(unique_vals) > 100,
        }
    
    def _query(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a pandas query expression."""
        expression = params.get("expression", "")
        
        if not expression:
            return {"error": "No query expression provided"}
        
        try:
            result = df.query(expression)
            return self._format_result(result)
        except Exception as e:
            return {"error": f"Query error: {str(e)}"}
    
    def _execute_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom pandas code."""
        code = params.get("code", "")
        
        if not code:
            return {"error": "No code provided"}
        
        # Get all dataframes for this chat
        dfs = self.df_registry.get_all_dataframes(self.chat_id)
        
        if not dfs:
            return {"error": "No data loaded"}
        
        # Primary df is the first one
        primary_name = list(dfs.keys())[0]
        dfs["df"] = dfs[primary_name]
        
        result = self.execution_guard.execute(code, dfs, "df")
        
        if result["success"]:
            return self._format_result(result["result"])
        else:
            return {"error": result.get("error", "Execution failed")}
    
    def _crosstab(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create cross-tabulation for categorical analysis."""
        row_column = params.get("row_column") or params.get("column")
        col_column = params.get("col_column") or params.get("column_2")
        
        if not row_column or not col_column:
            return {"error": "Both row_column and col_column are required for crosstab"}
        
        row_col = self._match_column(df, row_column)
        col_col = self._match_column(df, col_column)
        
        if not row_col:
            return {"error": f"Row column '{row_column}' not found", "available_columns": list(df.columns)}
        if not col_col:
            return {"error": f"Column '{col_column}' not found", "available_columns": list(df.columns)}
        
        try:
            result = pd.crosstab(df[row_col], df[col_col], margins=True, margins_name="Total")
            return self._format_result(result)
        except Exception as e:
            return {"error": f"Crosstab error: {str(e)}"}
    
    def _percentile(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate specific percentiles for a column."""
        column = params.get("column")
        percentiles = params.get("percentiles", [25, 50, 75, 90, 95, 99])
        
        if not column:
            return {"error": "Column is required for percentile calculation"}
        
        col = self._match_column(df, column)
        if not col:
            return {"error": f"Column '{column}' not found"}
        
        data = df[col].dropna()
        
        if len(data) == 0:
            return {"error": "No non-null values in column"}
        
        result = {}
        for p in percentiles:
            result[f"p{p}"] = round(float(data.quantile(p / 100)), 4)
        
        return {
            "success": True,
            "result_type": "percentiles",
            "column": col,
            "sample_size": len(data),
            "percentiles": result,
            "interpretation": f"Percentile analysis for {col}: median (p50) is {result.get('p50', 'N/A')}, "
                            f"top 10% values exceed {result.get('p90', 'N/A')}"
        }
    
    def _pivot_table(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a pivot table."""
        index = params.get("index")
        columns_param = params.get("columns")
        values = params.get("values")
        aggfunc = params.get("aggfunc", "mean")
        
        if not index:
            return {"error": "index is required for pivot table"}
        
        idx_col = self._match_column(df, index)
        if not idx_col:
            return {"error": f"Index column '{index}' not found"}
        
        try:
            pivot_params = {"index": idx_col, "aggfunc": aggfunc}
            
            if columns_param:
                col = self._match_column(df, columns_param)
                if col:
                    pivot_params["columns"] = col
            
            if values:
                val_col = self._match_column(df, values)
                if val_col:
                    pivot_params["values"] = val_col
            
            result = pd.pivot_table(df, **pivot_params)
            return self._format_result(result.reset_index())
        except Exception as e:
            return {"error": f"Pivot table error: {str(e)}"}
    
    def _correlation(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate correlation between two columns or matrix for all numeric."""
        col1 = params.get("column_1") or params.get("column")
        col2 = params.get("column_2")
        
        if col1 and col2:
            # Correlation between two specific columns
            c1 = self._match_column(df, col1)
            c2 = self._match_column(df, col2)
            
            if not c1:
                return {"error": f"Column '{col1}' not found"}
            if not c2:
                return {"error": f"Column '{col2}' not found"}
            
            data = df[[c1, c2]].dropna()
            if len(data) < 3:
                return {"error": "Insufficient non-null pairs for correlation"}
            
            corr = data[c1].corr(data[c2])
            
            strength = "very strong" if abs(corr) >= 0.8 else \
                      "strong" if abs(corr) >= 0.6 else \
                      "moderate" if abs(corr) >= 0.4 else \
                      "weak" if abs(corr) >= 0.2 else "very weak"
            
            return {
                "success": True,
                "result_type": "correlation",
                "column_1": c1,
                "column_2": c2,
                "correlation": round(float(corr), 4),
                "strength": strength,
                "direction": "positive" if corr > 0 else "negative",
                "sample_size": len(data),
                "interpretation": f"The correlation between {c1} and {c2} is {round(corr, 4)} ({strength} {('positive' if corr > 0 else 'negative')}). "
                                f"Based on {len(data)} data points."
            }
        else:
            # Correlation matrix for all numeric columns
            numeric_df = df.select_dtypes(include=[np.number])
            if len(numeric_df.columns) < 2:
                return {"error": "Need at least 2 numeric columns for correlation matrix"}
            
            corr_matrix = numeric_df.corr()
            return self._format_result(corr_matrix.reset_index())
    
    def _rolling(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate rolling window statistics."""
        column = params.get("column")
        window = params.get("window", 7)
        operation = params.get("rolling_operation", "mean")
        
        if not column:
            return {"error": "Column is required for rolling calculation"}
        
        col = self._match_column(df, column)
        if not col:
            return {"error": f"Column '{column}' not found"}
        
        try:
            data = df[col]
            if operation == "mean":
                result = data.rolling(window=window).mean()
            elif operation == "sum":
                result = data.rolling(window=window).sum()
            elif operation == "std":
                result = data.rolling(window=window).std()
            elif operation == "min":
                result = data.rolling(window=window).min()
            elif operation == "max":
                result = data.rolling(window=window).max()
            else:
                result = data.rolling(window=window).mean()
            
            result_df = pd.DataFrame({
                col: data,
                f"{col}_rolling_{operation}_{window}": result
            })
            
            return self._format_result(result_df.dropna())
        except Exception as e:
            return {"error": f"Rolling calculation error: {str(e)}"}
    
    def _match_column(self, df: pd.DataFrame, column: str) -> Optional[str]:
        """
        Smart column matching with proper precedence:
        1. Exact match
        2. Case-insensitive exact match (normalized)
        3. Best partial match (longest overlap wins)
        """
        # 1. Exact match
        if column in df.columns:
            return column
        
        # 2. Case-insensitive normalized match
        col_normalized = column.lower().replace(" ", "").replace("_", "").replace("(", "").replace(")", "")
        for c in df.columns:
            c_normalized = c.lower().replace(" ", "").replace("_", "").replace("(", "").replace(")", "")
            if c_normalized == col_normalized:
                return c
        
        # 3. Find best partial match
        search_lower = column.lower()
        candidates = []
        for c in df.columns:
            c_lower = c.lower()
            if search_lower in c_lower:
                candidates.append((c, len(c_lower) - len(search_lower)))
            elif c_lower in search_lower:
                candidates.append((c, 1000 + len(search_lower) - len(c_lower)))
        
        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]
        
        return None


def create_pandas_tool(chat_id: str) -> PandasTool:
    """Factory function to create a PandasTool."""
    return PandasTool(chat_id)

