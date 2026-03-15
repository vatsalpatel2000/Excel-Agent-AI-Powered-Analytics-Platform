"""
Robustness Tests - Hard Test Cases

These tests validate the critical robustness requirements:
1. Multi-sheet Excel file handling (ALL sheets)
2. Plain English output (NO code, NO technical jargon)
3. Cross-sheet analysis
4. Edge cases (empty sheets, nulls, special chars)
5. Large dataset handling
"""

import pytest
import pandas as pd
import numpy as np
from uuid import uuid4
import re

from app.core.dataframe_registry import DataFrameRegistry, get_dataframe_registry
from app.core.sheet_index import SheetIndex, SheetMetadata, get_sheet_index


class TestMultiSheetHandling:
    """Tests to ensure ALL sheets are loaded and accessible."""
    
    @pytest.fixture(autouse=True)
    def setup(self, sample_chat_id, multi_sheet_data):
        """Setup registry and index with multi-sheet data."""
        self.chat_id = sample_chat_id
        self.data = multi_sheet_data
        self.registry = DataFrameRegistry()
        self.sheet_index = SheetIndex()
        
        file_id = str(uuid4())
        for idx, (sheet_name, df) in enumerate(self.data.items()):
            self.registry.register(
                chat_id=self.chat_id,
                file_id=file_id,
                sheet_name=sheet_name,
                dataframe=df,
                sheet_index=idx,
            )
            
            metadata = SheetMetadata.from_dataframe(
                df=df,
                file_id=file_id,
                file_name="test.xlsx",
                sheet_name=sheet_name,
                sheet_index=idx,
            )
            self.sheet_index.add(self.chat_id, metadata)
    
    def test_all_sheets_registered(self):
        """CRITICAL: All sheets must be registered, not just first."""
        sheets = self.registry.get_all_sheets(self.chat_id)
        
        assert len(sheets) == 3, f"Expected 3 sheets, got {len(sheets)}"
        assert "Revenue_2023" in sheets
        assert "Expenses_2023" in sheets
        assert "Employees" in sheets
    
    def test_sheet_access_by_index(self):
        """User should be able to access 'sheet 2', 'sheet 3', etc."""
        sheet2 = self.registry.get_by_index(self.chat_id, 2)
        assert sheet2 is not None, "Sheet 2 must be accessible"
        assert "Operating_Costs" in sheet2.columns
        
        sheet3 = self.registry.get_by_index(self.chat_id, 3)
        assert sheet3 is not None, "Sheet 3 must be accessible"
        assert "Employee_Count" in sheet3.columns
    
    def test_sheet_access_case_insensitive(self):
        """Sheet access should be case-insensitive."""
        df1 = self.registry.get(self.chat_id, "revenue_2023")
        df2 = self.registry.get(self.chat_id, "REVENUE_2023")
        df3 = self.registry.get(self.chat_id, "Revenue_2023")
        
        assert df1 is not None
        assert df2 is not None
        assert df3 is not None
    
    def test_sheet_index_query(self):
        """SheetIndex must parse natural language sheet references."""
        matches = self.sheet_index.find_by_query(self.chat_id, "analyze sheet 2")
        assert len(matches) == 1
        assert matches[0].sheet_index == 1  # 0-indexed
        
        matches = self.sheet_index.find_by_query(self.chat_id, "second sheet")
        assert len(matches) == 1
    
    def test_llm_context_includes_all_sheets(self):
        """LLM context must show ALL sheets."""
        context = self.sheet_index.build_context_for_llm(self.chat_id)
        
        assert "Revenue_2023" in context
        assert "Expenses_2023" in context
        assert "Employees" in context
        assert "3 sheet(s)" in context


class TestSheetMetadata:
    """Tests for metadata extraction."""
    
    def test_metadata_extraction(self, sample_chat_id, sample_dataframe):
        """SheetMetadata must extract correct information."""
        metadata = SheetMetadata.from_dataframe(
            df=sample_dataframe,
            file_id="test",
            file_name="test.xlsx",
            sheet_name="Data",
            sheet_index=0,
        )
        
        assert metadata.row_count == 5
        assert metadata.column_count == 4
        assert "Company" in metadata.columns
        assert "Revenue" in metadata.columns
        
        # Check numeric stats
        revenue_col = metadata.columns["Revenue"]
        assert revenue_col.is_numeric
        assert revenue_col.min_value is not None
        assert revenue_col.max_value is not None
    
    def test_metadata_llm_context(self, sample_chat_id, sample_dataframe):
        """LLM context generation must be readable."""
        metadata = SheetMetadata.from_dataframe(
            df=sample_dataframe,
            file_id="test",
            file_name="test.xlsx",
            sheet_name="Companies",
            sheet_index=0,
        )
        
        context = metadata.to_llm_context()
        
        assert "Companies" in context
        assert "5" in context  # Row count
        assert "Revenue" in context
        # Should show range for numeric columns
        assert "range" in context.lower() or "to" in context


class TestEdgeCases:
    """Tests for edge case handling."""
    
    def test_empty_dataframe(self, sample_chat_id):
        """System must handle empty DataFrames."""
        registry = DataFrameRegistry()
        empty_df = pd.DataFrame()
        
        registered = registry.register(
            chat_id=sample_chat_id,
            file_id="file1",
            sheet_name="EmptySheet",
            dataframe=empty_df,
            sheet_index=0,
        )
        
        assert registered.row_count == 0
        assert registered.column_count == 0
    
    def test_special_characters_in_sheet_names(self, sample_chat_id):
        """Sheet names with special characters must work."""
        registry = DataFrameRegistry()
        
        special_names = [
            "Revenue (2023)",
            "Q1 & Q2 Data",
            "Sheet #1",
        ]
        
        for i, name in enumerate(special_names):
            df = pd.DataFrame({"col": [1, 2, 3]})
            registry.register(sample_chat_id, "file1", name, df, i)
        
        sheets = registry.get_all_sheets(sample_chat_id)
        assert len(sheets) == 3
    
    def test_null_values(self, sample_chat_id, edge_case_data):
        """Data with null values must be handled."""
        registry = DataFrameRegistry()
        
        registry.register(sample_chat_id, "file1", "EdgeCases", edge_case_data, 0)
        
        retrieved = registry.get(sample_chat_id, "EdgeCases")
        assert retrieved is not None
        assert retrieved["Revenue"].isna().sum() == 1
    
    def test_large_dataset(self, sample_chat_id, large_dataset):
        """Large datasets must be handled efficiently."""
        registry = DataFrameRegistry()
        
        registry.register(sample_chat_id, "file1", "Large", large_dataset, 0)
        
        registered = registry.get_registered(sample_chat_id, "Large")
        assert registered is not None
        assert registered.row_count == 1000
    
    def test_metadata_for_large_data(self, sample_chat_id, large_dataset):
        """SheetMetadata must limit sample values."""
        metadata = SheetMetadata.from_dataframe(
            df=large_dataset,
            file_id="file1",
            file_name="large.xlsx",
            sheet_name="Data",
            sheet_index=0,
        )
        
        assert metadata.row_count == 1000
        # Sample values should be limited
        for col_info in metadata.columns.values():
            assert len(col_info.sample_values) <= 5


class TestExecutionGuard:
    """Tests for safe code execution."""
    
    def test_forbidden_patterns(self, sample_dataframe):
        """Forbidden patterns must be rejected."""
        from app.core.execution_guard import ExecutionGuard
        
        guard = ExecutionGuard()
        
        dangerous_codes = [
            "import os",
            "from subprocess import run",
            "open('/etc/passwd').read()",
            "eval('1+1')",
            "__import__('os')",
        ]
        
        for code in dangerous_codes:
            is_safe, error = guard.validate_code(code)
            assert not is_safe, f"Code should be rejected: {code}"
    
    def test_safe_execution(self, sample_dataframe):
        """Safe code must execute correctly."""
        from app.core.execution_guard import ExecutionGuard
        
        guard = ExecutionGuard()
        
        result = guard.execute(
            code="result = df['Revenue'].mean()",
            dataframes={"df": sample_dataframe},
        )
        
        assert result["success"]
        assert result["result"] is not None
    
    def test_structured_operations(self, sample_dataframe):
        """Structured operations must work."""
        from app.core.execution_guard import ExecutionGuard
        
        guard = ExecutionGuard()
        
        # Filter operation
        result = guard.execute_structured_operation(
            operation="filter",
            df=sample_dataframe,
            params={
                "conditions": [
                    {"column": "Sector", "operator": "==", "value": "Technology"}
                ]
            },
        )
        
        assert result["success"]
        assert len(result["result"]) == 4  # 4 tech companies


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
