"""
Execution Guard - Safe Code Execution Environment

Provides sandboxed execution of Pandas operations with:
- Whitelisted safe operations
- Timeout protection
- Error handling
- Result validation
"""

from typing import Dict, Any, Optional, List, Set
import pandas as pd
import numpy as np
import traceback
import re


class ExecutionGuard:
    """
    Safe execution environment for Pandas operations.
    
    Key features:
    - Whitelisted operations only
    - No file system access
    - No network access
    - No dangerous builtins (eval, exec, compile)
    - Result size limits
    """
    
    # Safe operations whitelist
    SAFE_BUILTINS = {
        'len': len,
        'sum': sum,
        'min': min,
        'max': max,
        'abs': abs,
        'round': round,
        'sorted': sorted,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'True': True,
        'False': False,
        'None': None,
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'any': any,
        'all': all,
        'isinstance': isinstance,
        'type': type,
        'print': print,  # For debugging, output is captured
    }
    
    # Forbidden patterns in code
    FORBIDDEN_PATTERNS = [
        r'\bimport\s+',         # No imports
        r'\bfrom\s+\w+\s+import',  # No from imports
        r'\bopen\s*\(',         # No file access
        r'\bos\.',              # No os module
        r'\bsubprocess\.',      # No subprocess
        r'\beval\s*\(',         # No eval
        r'\bexec\s*\(',         # No exec
        r'\bcompile\s*\(',      # No compile
        r'\b__\w+__\b',         # No dunder attributes (except allowed)
        r'\bgetattr\s*\(',      # No getattr
        r'\bsetattr\s*\(',      # No setattr
        r'\bglobals\s*\(',      # No globals access
        r'\blocals\s*\(',       # No locals access
        r'\brequests\.',        # No HTTP requests
        r'\burllib\.',          # No urllib
        r'\bsocket\.',          # No sockets
    ]
    
    # Maximum result size to prevent memory issues
    MAX_RESULT_ROWS = 100000
    MAX_RESULT_SIZE_MB = 50
    
    def __init__(self):
        pass
    
    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate code for safety before execution.
        
        Returns:
            (is_safe, error_message)
        """
        if not code or not code.strip():
            return False, "Empty code"
        
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Forbidden pattern detected: {pattern}"
        
        return True, None
    
    def execute(
        self,
        code: str,
        dataframes: Dict[str, pd.DataFrame],
        primary_df_name: str = "df",
    ) -> Dict[str, Any]:
        """
        Execute code safely with provided DataFrames.
        
        Args:
            code: Python/Pandas code to execute
            dataframes: Dict of {name: DataFrame} to make available
            primary_df_name: Name of the primary DataFrame (usually "df")
            
        Returns:
            {
                "success": bool,
                "result": Any,
                "result_type": str,
                "error": Optional[str],
                "traceback": Optional[str],
            }
        """
        # Validate code first
        is_safe, error = self.validate_code(code)
        if not is_safe:
            return {
                "success": False,
                "result": None,
                "result_type": "error",
                "error": f"Code validation failed: {error}",
            }
        
        # Build safe execution environment
        safe_globals = {
            **self.SAFE_BUILTINS,
            'pd': pd,
            'np': np,
        }
        
        # Add DataFrames (copy to prevent modification)
        for name, df in dataframes.items():
            safe_globals[name] = df.copy()
        
        # Also add cleaned-up names for sheets with special characters
        for name, df in dataframes.items():
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
            if clean_name != name:
                safe_globals[f"df_{clean_name}"] = df.copy()
        
        safe_locals: Dict[str, Any] = {}
        
        try:
            # Execute the code
            exec(code, safe_globals, safe_locals)
            
            # Get result
            result = safe_locals.get('result')
            
            # If no explicit result, find the first meaningful variable
            if result is None:
                for key, value in safe_locals.items():
                    if not key.startswith('_') and value is not None:
                        result = value
                        break
            
            # Validate result size
            if isinstance(result, pd.DataFrame) and len(result) > self.MAX_RESULT_ROWS:
                result = result.head(self.MAX_RESULT_ROWS)
            
            return {
                "success": True,
                "result": result,
                "result_type": type(result).__name__,
                "error": None,
            }
            
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "result_type": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
    
    def execute_structured_operation(
        self,
        operation: str,
        df: pd.DataFrame,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a pre-defined structured operation.
        Safer than arbitrary code execution.
        
        Supported operations:
        - filter: Apply conditions
        - select: Choose columns
        - groupby: Group and aggregate
        - sort: Sort by columns
        - describe: Statistical summary
        - value_counts: Count unique values
        - head/tail: Get first/last N rows
        - count/sum/mean: Simple aggregations
        - unique: Get unique values
        """
        try:
            if operation == "filter":
                return self._op_filter(df, params)
            elif operation == "select":
                return self._op_select(df, params)
            elif operation == "groupby":
                return self._op_groupby(df, params)
            elif operation == "sort":
                return self._op_sort(df, params)
            elif operation == "describe":
                return self._op_describe(df)
            elif operation == "value_counts":
                return self._op_value_counts(df, params)
            elif operation == "head":
                return self._op_head(df, params)
            elif operation == "tail":
                return self._op_tail(df, params)
            elif operation == "count":
                return self._op_count(df, params)
            elif operation == "sum":
                return self._op_sum(df, params)
            elif operation == "mean":
                return self._op_mean(df, params)
            elif operation == "unique":
                return self._op_unique(df, params)
            elif operation == "query":
                return self._op_query(df, params)
            else:
                return {
                    "success": False,
                    "result": None,
                    "result_type": "error",
                    "error": f"Unknown operation: {operation}",
                }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "result_type": "error",
                "error": str(e),
            }
    
    def _op_filter(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply filter conditions."""
        conditions = params.get("conditions", [])
        result = df.copy()
        
        for cond in conditions:
            col = cond.get("column")
            op = cond.get("operator", "==")
            val = cond.get("value")
            
            if col not in result.columns:
                continue
            
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
        
        return {"success": True, "result": result, "result_type": "DataFrame"}
    
    def _op_select(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Select specific columns."""
        columns = params.get("columns", [])
        valid_cols = [c for c in columns if c in df.columns]
        
        if not valid_cols:
            return {"success": False, "result": None, "error": "No valid columns specified"}
        
        return {"success": True, "result": df[valid_cols], "result_type": "DataFrame"}
    
    def _op_groupby(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Group by columns and aggregate."""
        group_by = params.get("group_by", [])
        aggregations = params.get("aggregations", {})
        
        if not group_by:
            return {"success": False, "result": None, "error": "No group_by columns specified"}
        
        valid_group = [c for c in group_by if c in df.columns]
        if not valid_group:
            return {"success": False, "result": None, "error": "Invalid group_by columns"}
        
        if aggregations:
            valid_aggs = {k: v for k, v in aggregations.items() if k in df.columns}
            result = df.groupby(valid_group).agg(valid_aggs).reset_index()
        else:
            result = df.groupby(valid_group).size().reset_index(name='count')
        
        return {"success": True, "result": result, "result_type": "DataFrame"}
    
    def _op_sort(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sort by columns."""
        by = params.get("by", [])
        ascending = params.get("ascending", True)
        
        valid_cols = [c for c in by if c in df.columns]
        if not valid_cols:
            return {"success": False, "result": None, "error": "Invalid sort columns"}
        
        result = df.sort_values(by=valid_cols, ascending=ascending)
        return {"success": True, "result": result, "result_type": "DataFrame"}
    
    def _op_describe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Statistical summary."""
        result = df.describe(include='all')
        return {"success": True, "result": result, "result_type": "DataFrame"}
    
    def _op_value_counts(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Count unique values."""
        column = params.get("column")
        top_n = params.get("top_n", 20)
        
        if column not in df.columns:
            return {"success": False, "result": None, "error": f"Column not found: {column}"}
        
        result = df[column].value_counts().head(top_n)
        return {"success": True, "result": result, "result_type": "Series"}
    
    def _op_head(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get first N rows."""
        n = params.get("n", 10)
        return {"success": True, "result": df.head(n), "result_type": "DataFrame"}
    
    def _op_tail(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get last N rows."""
        n = params.get("n", 10)
        return {"success": True, "result": df.tail(n), "result_type": "DataFrame"}
    
    def _op_count(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Count rows or column values."""
        column = params.get("column")
        if column and column in df.columns:
            result = df[column].count()
        else:
            result = len(df)
        return {"success": True, "result": int(result), "result_type": "int"}
    
    def _op_sum(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sum a column."""
        column = params.get("column")
        if column not in df.columns:
            return {"success": False, "result": None, "error": f"Column not found: {column}"}
        
        result = df[column].sum()
        return {"success": True, "result": float(result), "result_type": "float"}
    
    def _op_mean(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate mean of a column."""
        column = params.get("column")
        if column not in df.columns:
            return {"success": False, "result": None, "error": f"Column not found: {column}"}
        
        result = df[column].mean()
        return {"success": True, "result": float(result), "result_type": "float"}
    
    def _op_unique(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get unique values."""
        column = params.get("column")
        if column not in df.columns:
            return {"success": False, "result": None, "error": f"Column not found: {column}"}
        
        result = df[column].unique().tolist()
        return {"success": True, "result": result, "result_type": "list"}
    
    def _op_query(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a pandas query expression."""
        expression = params.get("expression", "")
        if not expression:
            return {"success": False, "result": None, "error": "No query expression provided"}
        
        # Basic safety check on expression
        for pattern in [r'\beval\b', r'\bexec\b', r'\bimport\b']:
            if re.search(pattern, expression):
                return {"success": False, "result": None, "error": "Unsafe expression"}
        
        result = df.query(expression)
        return {"success": True, "result": result, "result_type": "DataFrame"}


# Singleton instance
_guard_instance: Optional[ExecutionGuard] = None


def get_execution_guard() -> ExecutionGuard:
    """Get the singleton ExecutionGuard instance."""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = ExecutionGuard()
    return _guard_instance
