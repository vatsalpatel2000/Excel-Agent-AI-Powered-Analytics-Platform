"""
Test Configuration - Pytest Fixtures

Provides common fixtures for testing the Excel Agent backend.
"""

import pytest
import pandas as pd
import numpy as np
from uuid import uuid4
from typing import Generator


@pytest.fixture
def sample_chat_id() -> str:
    """Generate unique chat ID for each test."""
    return str(uuid4())


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Sample DataFrame for testing."""
    return pd.DataFrame({
        "Company": ["Apple Inc.", "Microsoft Corp", "Amazon.com", "Alphabet Inc.", "Meta Platforms"],
        "Revenue": [394328, 198270, 513983, 307394, 134902],
        "Employees": [164000, 221000, 1541000, 190234, 86482],
        "Sector": ["Technology", "Technology", "Consumer Discretionary", "Technology", "Technology"],
    })


@pytest.fixture
def multi_sheet_data() -> dict:
    """Multi-sheet data for testing."""
    return {
        "Revenue_2023": pd.DataFrame({
            "Company": ["Apple Inc.", "Microsoft Corp", "Amazon.com"],
            "Q1_Revenue": [117543, 52857, 127358],
            "Q2_Revenue": [81797, 56189, 121234],
        }),
        "Expenses_2023": pd.DataFrame({
            "Company": ["Apple Inc.", "Microsoft Corp", "Amazon.com"],
            "Operating_Costs": [45000, 32000, 89000],
            "R&D_Spending": [25000, 24000, 42000],
        }),
        "Employees": pd.DataFrame({
            "Company": ["Apple Inc.", "Microsoft Corp", "Amazon.com"],
            "Employee_Count": [164000, 221000, 1541000],
            "Avg_Salary": [145000, 158000, 95000],
        }),
    }


@pytest.fixture
def large_dataset() -> pd.DataFrame:
    """Large dataset for stress testing."""
    np.random.seed(42)
    n = 1000
    return pd.DataFrame({
        "ID": range(1, n + 1),
        "Company": [f"Company_{i}" for i in range(1, n + 1)],
        "Revenue": np.random.randint(1000000, 1000000000, n),
        "Employees": np.random.randint(100, 100000, n),
        "Founded": np.random.randint(1950, 2023, n),
    })


@pytest.fixture
def edge_case_data() -> pd.DataFrame:
    """Data with edge cases for testing."""
    return pd.DataFrame({
        "Company": ["Valid Co.", None, "Special & Co.", "Números SA", "", "  Spaces  "],
        "Revenue": [1000000, np.nan, 2500000, 500000, 0, 750000],
        "Notes": [None, None, "Important!", None, None, None],
    })
