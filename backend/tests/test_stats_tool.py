"""
Stats Tool Tests - Advanced Statistical Analysis

Tests for the stats_tool.py functionality:
- Correlation analysis
- Distribution analysis  
- Outlier detection
- Percentile calculations
- Comparative statistics
- Summary insights
"""

import pytest
import pandas as pd
import numpy as np
from uuid import uuid4

from app.tools.stats_tool import StatsTool, create_stats_tool
from app.core.dataframe_registry import DataFrameRegistry, get_dataframe_registry


class TestCorrelationAnalysis:
    """Tests for correlation functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data with correlated columns."""
        self.chat_id = str(uuid4())
        self.registry = DataFrameRegistry()
        
        # Create data with known correlations
        np.random.seed(42)
        n = 100
        x = np.random.normal(0, 1, n)
        y_strong = x * 0.9 + np.random.normal(0, 0.1, n)  # Strong positive
        y_weak = x * 0.2 + np.random.normal(0, 0.8, n)    # Weak positive
        y_negative = -x * 0.8 + np.random.normal(0, 0.2, n)  # Strong negative
        
        self.df = pd.DataFrame({
            "X": x,
            "Y_Strong": y_strong,
            "Y_Weak": y_weak,
            "Y_Negative": y_negative,
            "Category": ["A", "B", "C", "D"] * 25,
        })
        
        self.registry.register(
            chat_id=self.chat_id,
            file_id="test",
            sheet_name="Test",
            dataframe=self.df,
            sheet_index=0,
        )
    
    def test_correlation_matrix(self):
        """Test correlation matrix generation."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("correlation_matrix", {"sheet_name": "Test"})
        
        assert result.get("success") is True
        assert "correlation_matrix" in result
        assert "strongest_correlations" in result
        assert len(result["numeric_columns"]) >= 3
    
    def test_two_column_correlation(self):
        """Test correlation between two specific columns."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("correlation", {
            "sheet_name": "Test",
            "column_1": "X",
            "column_2": "Y_Strong",
        })
        
        assert result.get("success") is True
        assert "pearson_correlation" in result
        
        # Strong positive correlation should be > 0.8
        corr = result["pearson_correlation"]["value"]
        assert corr > 0.8, f"Expected strong correlation > 0.8, got {corr}"
    
    def test_correlation_interpretation(self):
        """Test that correlation includes interpretation."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("correlation", {
            "sheet_name": "Test",
            "column_1": "X",
            "column_2": "Y_Negative",
        })
        
        assert "interpretation" in result
        assert "negative" in result["interpretation"].lower()


class TestDistributionAnalysis:
    """Tests for distribution analysis."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data."""
        self.chat_id = str(uuid4())
        self.registry = DataFrameRegistry()
        
        np.random.seed(42)
        
        self.df = pd.DataFrame({
            "Normal": np.random.normal(100, 15, 200),
            "Skewed": np.random.exponential(10, 200),
            "Uniform": np.random.uniform(0, 100, 200),
        })
        
        self.registry.register(
            chat_id=self.chat_id,
            file_id="test",
            sheet_name="Distributions",
            dataframe=self.df,
            sheet_index=0,
        )
    
    def test_distribution_analysis_single_column(self):
        """Test distribution analysis for a single column."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("distribution_analysis", {
            "sheet_name": "Distributions",
            "column": "Normal",
        })
        
        assert result.get("success") is True
        assert "basic_stats" in result
        assert "quartiles" in result
        assert "shape" in result
        
        # Check basic stats are correct
        assert "mean" in result["basic_stats"]
        assert "median" in result["basic_stats"]
        assert "std" in result["basic_stats"]
    
    def test_skewness_detection(self):
        """Test that skewed distributions are detected."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("distribution_analysis", {
            "sheet_name": "Distributions",
            "column": "Skewed",
        })
        
        assert result.get("success") is True
        assert result["shape"]["skewness"] > 0.5  # Right-skewed
        assert "right" in result["shape"]["skewness_interpretation"].lower()


class TestOutlierDetection:
    """Tests for outlier detection."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data with outliers."""
        self.chat_id = str(uuid4())
        self.registry = DataFrameRegistry()
        
        # Data with known outliers
        values = list(range(100)) + [500, 600, 700]  # 3 obvious outliers
        
        self.df = pd.DataFrame({
            "Values": values,
            "Clean": range(103),
        })
        
        self.registry.register(
            chat_id=self.chat_id,
            file_id="test",
            sheet_name="Outliers",
            dataframe=self.df,
            sheet_index=0,
        )
    
    def test_iqr_outlier_detection(self):
        """Test IQR-based outlier detection."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("outlier_detection", {
            "sheet_name": "Outliers",
            "column": "Values",
            "method": "iqr",
        })
        
        assert result.get("success") is True
        assert "Values" in result["results"]
        
        iqr_result = result["results"]["Values"]["iqr_method"]
        assert iqr_result["outlier_count"] >= 3  # Should detect at least our 3 outliers


class TestPercentileAnalysis:
    """Tests for percentile calculations."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data."""
        self.chat_id = str(uuid4())
        self.registry = DataFrameRegistry()
        
        self.df = pd.DataFrame({
            "Values": list(range(1, 101)),  # 1 to 100
        })
        
        self.registry.register(
            chat_id=self.chat_id,
            file_id="test",
            sheet_name="Percentiles",
            dataframe=self.df,
            sheet_index=0,
        )
    
    def test_percentile_calculation(self):
        """Test percentile calculations."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("percentile_analysis", {
            "sheet_name": "Percentiles",
            "column": "Values",
            "percentiles": [25, 50, 75],
        })
        
        assert result.get("success") is True
        assert "percentiles" in result
        
        # For 1-100, median should be ~50.5
        assert 50 <= result["percentiles"]["p50"] <= 51


class TestComparativeStats:
    """Tests for comparative statistics."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup grouped test data."""
        self.chat_id = str(uuid4())
        self.registry = DataFrameRegistry()
        
        np.random.seed(42)
        
        self.df = pd.DataFrame({
            "Region": ["North", "South", "East", "West"] * 25,
            "Sales": np.random.normal([100, 150, 80, 120] * 25, 20),
        })
        
        self.registry.register(
            chat_id=self.chat_id,
            file_id="test",
            sheet_name="Regional",
            dataframe=self.df,
            sheet_index=0,
        )
    
    def test_comparative_stats(self):
        """Test group comparison."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("comparative_stats", {
            "sheet_name": "Regional",
            "group_column": "Region",
            "value_column": "Sales",
        })
        
        assert result.get("success") is True
        assert result["number_of_groups"] == 4
        assert len(result["group_statistics"]) == 4
        
        # Check that each group has expected statistics
        for group_stat in result["group_statistics"]:
            assert "mean" in group_stat
            assert "median" in group_stat
            assert "count" in group_stat


class TestSummaryInsights:
    """Tests for summary insights generation."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data."""
        self.chat_id = str(uuid4())
        self.registry = DataFrameRegistry()
        
        self.df = pd.DataFrame({
            "Revenue": [1000, 2000, 1500, 3000, 2500],
            "Employees": [10, 20, 15, 30, 25],
            "Company": ["A", "B", "C", "D", "E"],
        })
        
        self.registry.register(
            chat_id=self.chat_id,
            file_id="test",
            sheet_name="Companies",
            dataframe=self.df,
            sheet_index=0,
        )
    
    def test_summary_insights(self):
        """Test summary insights generation."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("summary_insights", {
            "sheet_name": "Companies",
        })
        
        assert result.get("success") is True
        assert "plain_english" in result
        assert "dataset_shape" in result
    
    def test_column_insights(self):
        """Test single column insights."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("summary_insights", {
            "sheet_name": "Companies",
            "column": "Revenue",
        })
        
        assert result.get("success") is True
        assert "statistics" in result
        assert "plain_english" in result
        assert "Revenue" in result["plain_english"]


class TestFullStatisticalSummary:
    """Tests for full statistical summary."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup comprehensive test data."""
        self.chat_id = str(uuid4())
        self.registry = DataFrameRegistry()
        
        np.random.seed(42)
        
        self.df = pd.DataFrame({
            "Revenue": np.random.normal(10000, 2000, 50),
            "Employees": np.random.randint(10, 100, 50),
            "Sector": np.random.choice(["Tech", "Finance", "Healthcare"], 50),
            "Country": np.random.choice(["USA", "UK", "Canada"], 50),
        })
        
        # Add some missing values
        self.df.loc[0:5, "Revenue"] = np.nan
        
        self.registry.register(
            chat_id=self.chat_id,
            file_id="test",
            sheet_name="FullData",
            dataframe=self.df,
            sheet_index=0,
        )
    
    def test_full_summary(self):
        """Test full statistical summary."""
        tool = StatsTool(self.chat_id)
        tool.df_registry = self.registry
        
        result = tool.execute("full_statistical_summary", {
            "sheet_name": "FullData",
        })
        
        assert result.get("success") is True
        assert "dataset_overview" in result
        assert "numeric_summary" in result
        assert "categorical_summary" in result
        assert "interpretation" in result
        
        # Check overview
        overview = result["dataset_overview"]
        assert overview["total_rows"] == 50
        assert overview["total_columns"] == 4
        assert overview["missing_values_total"] > 0  # We added missing values


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
