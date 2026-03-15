"""
Stats Tool - Advanced Statistical Analysis

Production-grade statistical analysis beyond basic pandas operations.
Provides deep insights with plain English explanations.
"""

from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
import logging

from app.core import get_dataframe_registry, get_sheet_index
from app.config import settings

logger = logging.getLogger(__name__)


class StatsTool:
    """
    Advanced Statistical Analysis Tool.
    
    Provides deep statistical analysis capabilities:
    - Correlation analysis (Pearson, Spearman)
    - Distribution analysis (skewness, kurtosis, normality)
    - Outlier detection (IQR, Z-score)
    - Percentile analysis
    - Comparative statistics
    - Trend analysis
    - Summary insights with plain English explanations
    """
    
    MAX_RESULT_ROWS = 5000
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.df_registry = get_dataframe_registry()
        self.sheet_index = get_sheet_index()
    
    def execute(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a statistical analysis operation."""
        sheet_name = params.get("sheet_name")
        df = self._get_dataframe(sheet_name)
        
        if df is None:
            available = self.df_registry.get_all_sheets(self.chat_id)
            return {
                "error": f"Sheet not found: {sheet_name}",
                "available_sheets": available,
            }
        
        operations_map = {
            "correlation_matrix": self._correlation_matrix,
            "correlation": self._column_correlation,
            "distribution_analysis": self._distribution_analysis,
            "outlier_detection": self._outlier_detection,
            "percentile_analysis": self._percentile_analysis,
            "comparative_stats": self._comparative_stats,
            "trend_analysis": self._trend_analysis,
            "summary_insights": self._summary_insights,
            "full_statistical_summary": self._full_statistical_summary,
        }
        
        if operation not in operations_map:
            return {"error": f"Unknown operation: {operation}", "available_operations": list(operations_map.keys())}
        
        try:
            return operations_map[operation](df, params)
        except Exception as e:
            logger.exception(f"Stats tool error: {e}")
            return {"error": str(e)}
    
    def _get_dataframe(self, sheet_name: Optional[str]) -> Optional[pd.DataFrame]:
        """Get DataFrame by name or return first sheet."""
        if sheet_name:
            df = self.df_registry.get(self.chat_id, sheet_name)
            if df is not None:
                return df
            df = self.df_registry.get_by_query(self.chat_id, sheet_name)
            if df is not None:
                return df
        
        sheets = self.df_registry.get_all_sheets(self.chat_id)
        if sheets:
            return self.df_registry.get(self.chat_id, sheets[0])
        return None
    
    def _correlation_matrix(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compute full correlation matrix for all numeric columns."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if len(numeric_cols) < 2:
            return {
                "error": "Need at least 2 numeric columns for correlation analysis",
                "numeric_columns_found": len(numeric_cols),
            }
        
        # Compute correlation matrix
        corr_matrix = df[numeric_cols].corr()
        
        # Find strongest correlations (excluding self-correlations)
        correlations = []
        for i, col1 in enumerate(numeric_cols):
            for j, col2 in enumerate(numeric_cols):
                if i < j:  # Upper triangle only
                    corr_value = corr_matrix.loc[col1, col2]
                    if pd.notna(corr_value):
                        correlations.append({
                            "column_1": col1,
                            "column_2": col2,
                            "correlation": round(float(corr_value), 4),
                            "strength": self._interpret_correlation(corr_value),
                            "direction": "positive" if corr_value > 0 else "negative",
                        })
        
        # Sort by absolute correlation
        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        
        # Convert matrix to serializable format
        matrix_dict = {}
        for col in numeric_cols:
            matrix_dict[col] = {c: round(float(corr_matrix.loc[col, c]), 4) for c in numeric_cols}
        
        return {
            "success": True,
            "operation": "correlation_matrix",
            "numeric_columns": numeric_cols,
            "sample_size": len(df),
            "correlation_matrix": matrix_dict,
            "strongest_correlations": correlations[:10],
            "interpretation": self._generate_correlation_interpretation(correlations[:5]),
        }
    
    def _column_correlation(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compute correlation between two specific columns."""
        col1 = params.get("column_1") or params.get("column")
        col2 = params.get("column_2")
        
        if not col1 or not col2:
            return {"error": "Both column_1 and column_2 are required"}
        
        # Case-insensitive column matching
        col1_matched = self._match_column(df, col1)
        col2_matched = self._match_column(df, col2)
        
        if not col1_matched:
            return {"error": f"Column '{col1}' not found", "available_columns": list(df.columns)}
        if not col2_matched:
            return {"error": f"Column '{col2}' not found", "available_columns": list(df.columns)}
        
        # Get clean data
        data = df[[col1_matched, col2_matched]].dropna()
        
        if len(data) < 3:
            return {"error": "Insufficient data for correlation (need at least 3 non-null pairs)"}
        
        # Compute correlations
        pearson_corr, pearson_p = scipy_stats.pearsonr(data[col1_matched], data[col2_matched])
        spearman_corr, spearman_p = scipy_stats.spearmanr(data[col1_matched], data[col2_matched])
        
        return {
            "success": True,
            "operation": "correlation",
            "column_1": col1_matched,
            "column_2": col2_matched,
            "sample_size": len(data),
            "pearson_correlation": {
                "value": round(float(pearson_corr), 4),
                "p_value": round(float(pearson_p), 6),
                "significant": pearson_p < 0.05,
                "strength": self._interpret_correlation(pearson_corr),
            },
            "spearman_correlation": {
                "value": round(float(spearman_corr), 4),
                "p_value": round(float(spearman_p), 6),
                "significant": spearman_p < 0.05,
            },
            "interpretation": self._generate_single_correlation_interpretation(
                col1_matched, col2_matched, pearson_corr, pearson_p, len(data)
            ),
        }
    
    def _distribution_analysis(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze distribution of a numeric column."""
        column = params.get("column")
        
        if not column:
            # Analyze all numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_cols:
                return {"error": "No numeric columns found"}
            
            results = {}
            for col in numeric_cols[:10]:  # Limit to 10 columns
                results[col] = self._analyze_single_distribution(df[col].dropna())
            
            return {
                "success": True,
                "operation": "distribution_analysis",
                "columns_analyzed": list(results.keys()),
                "distributions": results,
            }
        
        col_matched = self._match_column(df, column)
        if not col_matched:
            return {"error": f"Column '{column}' not found", "available_columns": list(df.columns)}
        
        data = df[col_matched].dropna()
        
        if len(data) < 3:
            return {"error": "Insufficient data for distribution analysis"}
        
        dist_analysis = self._analyze_single_distribution(data)
        dist_analysis["column"] = col_matched
        dist_analysis["success"] = True
        dist_analysis["operation"] = "distribution_analysis"
        
        return dist_analysis
    
    def _analyze_single_distribution(self, data: pd.Series) -> Dict[str, Any]:
        """Analyze distribution of a single series."""
        n = len(data)
        
        # Basic stats
        basic_stats = {
            "count": int(n),
            "mean": round(float(data.mean()), 4),
            "median": round(float(data.median()), 4),
            "std": round(float(data.std()), 4),
            "variance": round(float(data.var()), 4),
            "min": round(float(data.min()), 4),
            "max": round(float(data.max()), 4),
            "range": round(float(data.max() - data.min()), 4),
        }
        
        # Quartiles
        quartiles = {
            "q1": round(float(data.quantile(0.25)), 4),
            "q2_median": round(float(data.quantile(0.50)), 4),
            "q3": round(float(data.quantile(0.75)), 4),
            "iqr": round(float(data.quantile(0.75) - data.quantile(0.25)), 4),
        }
        
        # Distribution shape
        skewness = float(data.skew())
        kurtosis = float(data.kurtosis())
        
        shape = {
            "skewness": round(skewness, 4),
            "skewness_interpretation": self._interpret_skewness(skewness),
            "kurtosis": round(kurtosis, 4),
            "kurtosis_interpretation": self._interpret_kurtosis(kurtosis),
        }
        
        # Normality test (if enough data)
        normality = {"tested": False}
        if 8 <= n <= 5000:
            try:
                stat, p_value = scipy_stats.shapiro(data.sample(min(n, 5000)))
                normality = {
                    "tested": True,
                    "test": "Shapiro-Wilk",
                    "statistic": round(float(stat), 4),
                    "p_value": round(float(p_value), 6),
                    "is_normal": p_value > 0.05,
                    "interpretation": "Data appears normally distributed" if p_value > 0.05 else "Data is NOT normally distributed",
                }
            except Exception:
                pass
        
        return {
            "basic_stats": basic_stats,
            "quartiles": quartiles,
            "shape": shape,
            "normality": normality,
            "interpretation": self._generate_distribution_interpretation(basic_stats, shape, quartiles),
        }
    
    def _outlier_detection(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Detect outliers using IQR and Z-score methods."""
        column = params.get("column")
        method = params.get("method", "both")  # iqr, zscore, or both
        
        results = {}
        columns_to_analyze = []
        
        if column:
            col_matched = self._match_column(df, column)
            if not col_matched:
                return {"error": f"Column '{column}' not found"}
            columns_to_analyze = [col_matched]
        else:
            columns_to_analyze = df.select_dtypes(include=[np.number]).columns.tolist()[:10]
        
        for col in columns_to_analyze:
            data = df[col].dropna()
            if len(data) < 4:
                continue
            
            col_result = {"column": col, "total_values": len(data)}
            
            if method in ["iqr", "both"]:
                q1 = data.quantile(0.25)
                q3 = data.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                iqr_outliers = data[(data < lower_bound) | (data > upper_bound)]
                
                col_result["iqr_method"] = {
                    "lower_bound": round(float(lower_bound), 4),
                    "upper_bound": round(float(upper_bound), 4),
                    "outlier_count": len(iqr_outliers),
                    "outlier_percentage": round(100 * len(iqr_outliers) / len(data), 2),
                    "outlier_values": [round(float(x), 4) for x in iqr_outliers.head(10).tolist()],
                }
            
            if method in ["zscore", "both"]:
                z_scores = np.abs(scipy_stats.zscore(data))
                zscore_outliers = data[z_scores > 3]
                
                col_result["zscore_method"] = {
                    "threshold": 3.0,
                    "outlier_count": len(zscore_outliers),
                    "outlier_percentage": round(100 * len(zscore_outliers) / len(data), 2),
                    "outlier_values": [round(float(x), 4) for x in zscore_outliers.head(10).tolist()],
                }
            
            results[col] = col_result
        
        return {
            "success": True,
            "operation": "outlier_detection",
            "method": method,
            "columns_analyzed": list(results.keys()),
            "results": results,
            "interpretation": self._generate_outlier_interpretation(results),
        }
    
    def _percentile_analysis(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate specific percentiles for a column."""
        column = params.get("column")
        percentiles = params.get("percentiles", [5, 10, 25, 50, 75, 90, 95, 99])
        
        if not column:
            return {"error": "column parameter is required"}
        
        col_matched = self._match_column(df, column)
        if not col_matched:
            return {"error": f"Column '{column}' not found"}
        
        data = df[col_matched].dropna()
        
        if len(data) < 4:
            return {"error": "Insufficient data for percentile analysis"}
        
        percentile_values = {}
        for p in percentiles:
            percentile_values[f"p{p}"] = round(float(data.quantile(p / 100)), 4)
        
        return {
            "success": True,
            "operation": "percentile_analysis",
            "column": col_matched,
            "sample_size": len(data),
            "percentiles": percentile_values,
            "interpretation": f"Percentile analysis for {col_matched}: The median (50th percentile) is {percentile_values.get('p50', 'N/A')}. "
                            f"The top 10% of values are above {percentile_values.get('p90', 'N/A')}, "
                            f"while the bottom 10% are below {percentile_values.get('p10', 'N/A')}.",
        }
    
    def _comparative_stats(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compare statistics across groups."""
        group_column = params.get("group_column") or params.get("group_by")
        value_column = params.get("value_column") or params.get("column")
        
        if not group_column or not value_column:
            return {"error": "Both group_column and value_column are required"}
        
        group_col_matched = self._match_column(df, group_column)
        value_col_matched = self._match_column(df, value_column)
        
        if not group_col_matched:
            return {"error": f"Group column '{group_column}' not found"}
        if not value_col_matched:
            return {"error": f"Value column '{value_column}' not found"}
        
        groups = df.groupby(group_col_matched)[value_col_matched]
        
        group_stats = []
        for name, group_data in groups:
            if len(group_data.dropna()) < 1:
                continue
            data = group_data.dropna()
            group_stats.append({
                "group": str(name),
                "count": int(len(data)),
                "mean": round(float(data.mean()), 4),
                "median": round(float(data.median()), 4),
                "std": round(float(data.std()), 4) if len(data) > 1 else 0,
                "min": round(float(data.min()), 4),
                "max": round(float(data.max()), 4),
            })
        
        # Sort by mean descending
        group_stats.sort(key=lambda x: x["mean"], reverse=True)
        
        # Overall statistics
        overall_mean = df[value_col_matched].mean()
        
        return {
            "success": True,
            "operation": "comparative_stats",
            "group_column": group_col_matched,
            "value_column": value_col_matched,
            "number_of_groups": len(group_stats),
            "overall_mean": round(float(overall_mean), 4),
            "group_statistics": group_stats,
            "interpretation": self._generate_comparative_interpretation(group_stats, value_col_matched),
        }
    
    def _trend_analysis(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trends over time or ordered data."""
        value_column = params.get("column") or params.get("value_column")
        time_column = params.get("time_column") or params.get("date_column")
        
        if not value_column:
            return {"error": "value_column is required"}
        
        value_col_matched = self._match_column(df, value_column)
        if not value_col_matched:
            return {"error": f"Value column '{value_column}' not found"}
        
        # If time column specified, sort by it
        if time_column:
            time_col_matched = self._match_column(df, time_column)
            if time_col_matched:
                df = df.sort_values(time_col_matched)
        
        data = df[value_col_matched].dropna()
        
        if len(data) < 5:
            return {"error": "Insufficient data for trend analysis (need at least 5 points)"}
        
        # Linear regression for trend
        x = np.arange(len(data))
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, data)
        
        # Calculate moving averages
        ma_5 = data.rolling(window=min(5, len(data))).mean().dropna().tolist()[-5:]
        ma_10 = data.rolling(window=min(10, len(data))).mean().dropna().tolist()[-5:] if len(data) >= 10 else []
        
        # Determine trend direction
        trend_direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
        trend_strength = abs(r_value)
        
        return {
            "success": True,
            "operation": "trend_analysis",
            "column": value_col_matched,
            "data_points": len(data),
            "trend": {
                "direction": trend_direction,
                "slope": round(float(slope), 6),
                "r_squared": round(float(r_value ** 2), 4),
                "strength": "strong" if trend_strength > 0.7 else "moderate" if trend_strength > 0.4 else "weak",
                "p_value": round(float(p_value), 6),
                "significant": p_value < 0.05,
            },
            "recent_moving_averages": {
                "ma_5": [round(float(x), 4) for x in ma_5],
                "ma_10": [round(float(x), 4) for x in ma_10] if ma_10 else None,
            },
            "interpretation": f"The {value_col_matched} shows a {trend_direction} trend. "
                            f"The R-squared value of {round(r_value ** 2, 4)} indicates that "
                            f"{'the trend is statistically significant' if p_value < 0.05 else 'the trend may not be statistically significant'}. "
                            f"On average, the value changes by {round(slope, 4)} per unit.",
        }
    
    def _summary_insights(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive summary insights in plain English."""
        column = params.get("column")
        
        if column:
            col_matched = self._match_column(df, column)
            if not col_matched:
                return {"error": f"Column '{column}' not found"}
            return self._generate_column_insights(df, col_matched)
        
        # Full dataset insights
        return self._generate_dataset_insights(df)
    
    def _full_statistical_summary(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive statistical summary of the entire dataset."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        summary = {
            "success": True,
            "operation": "full_statistical_summary",
            "dataset_overview": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "numeric_columns": len(numeric_cols),
                "categorical_columns": len(categorical_cols),
                "missing_values_total": int(df.isnull().sum().sum()),
                "missing_percentage": round(100 * df.isnull().sum().sum() / (len(df) * len(df.columns)), 2),
            },
            "numeric_summary": {},
            "categorical_summary": {},
        }
        
        # Numeric column summaries
        for col in numeric_cols[:15]:  # Limit for performance
            data = df[col].dropna()
            if len(data) > 0:
                summary["numeric_summary"][col] = {
                    "count": int(len(data)),
                    "mean": round(float(data.mean()), 4),
                    "median": round(float(data.median()), 4),
                    "std": round(float(data.std()), 4) if len(data) > 1 else 0,
                    "min": round(float(data.min()), 4),
                    "max": round(float(data.max()), 4),
                    "missing": int(df[col].isnull().sum()),
                }
        
        # Categorical column summaries
        for col in categorical_cols[:10]:
            value_counts = df[col].value_counts()
            summary["categorical_summary"][col] = {
                "unique_values": int(df[col].nunique()),
                "most_common": str(value_counts.index[0]) if len(value_counts) > 0 else None,
                "most_common_count": int(value_counts.iloc[0]) if len(value_counts) > 0 else 0,
                "missing": int(df[col].isnull().sum()),
            }
        
        summary["interpretation"] = self._generate_full_summary_interpretation(summary)
        
        return summary
    
    def _generate_column_insights(self, df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """Generate insights for a single column."""
        data = df[column].dropna()
        is_numeric = pd.api.types.is_numeric_dtype(data)
        
        insights = {
            "success": True,
            "column": column,
            "data_type": "numeric" if is_numeric else "categorical",
            "total_values": len(df[column]),
            "non_null_values": len(data),
            "missing_count": int(df[column].isnull().sum()),
            "missing_percentage": round(100 * df[column].isnull().sum() / len(df[column]), 2),
        }
        
        if is_numeric:
            insights["statistics"] = {
                "mean": round(float(data.mean()), 4),
                "median": round(float(data.median()), 4),
                "std": round(float(data.std()), 4) if len(data) > 1 else 0,
                "min": round(float(data.min()), 4),
                "max": round(float(data.max()), 4),
                "range": round(float(data.max() - data.min()), 4),
            }
            
            # Plain English interpretation
            mean_val = insights["statistics"]["mean"]
            median_val = insights["statistics"]["median"]
            
            insights["plain_english"] = (
                f"The {column} column contains {len(data):,} values. "
                f"The average (mean) is {mean_val:,.2f}, while the middle value (median) is {median_val:,.2f}. "
                f"Values range from {insights['statistics']['min']:,.2f} to {insights['statistics']['max']:,.2f}. "
            )
            
            if abs(mean_val - median_val) / max(abs(mean_val), 1) > 0.1:
                if mean_val > median_val:
                    insights["plain_english"] += "The mean is higher than median, suggesting some high values are pulling the average up (right-skewed distribution). "
                else:
                    insights["plain_english"] += "The mean is lower than median, suggesting some low values are pulling the average down (left-skewed distribution). "
        else:
            unique_count = data.nunique()
            value_counts = data.value_counts().head(5)
            
            insights["statistics"] = {
                "unique_values": int(unique_count),
                "top_values": {str(k): int(v) for k, v in value_counts.items()},
            }
            
            insights["plain_english"] = (
                f"The {column} column contains {len(data):,} values with {unique_count:,} unique categories. "
                f"The most common value is '{value_counts.index[0]}' appearing {value_counts.iloc[0]:,} times "
                f"({round(100 * value_counts.iloc[0] / len(data), 1)}% of all values)."
            )
        
        return insights
    
    def _generate_dataset_insights(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate insights for the entire dataset."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        insights = {
            "success": True,
            "operation": "summary_insights",
            "dataset_shape": {"rows": len(df), "columns": len(df.columns)},
            "column_types": {
                "numeric": len(numeric_cols),
                "non_numeric": len(df.columns) - len(numeric_cols),
            },
            "data_quality": {
                "total_missing": int(df.isnull().sum().sum()),
                "missing_percentage": round(100 * df.isnull().sum().sum() / (len(df) * len(df.columns)), 2),
                "complete_rows": int((~df.isnull().any(axis=1)).sum()),
                "complete_rows_percentage": round(100 * (~df.isnull().any(axis=1)).sum() / len(df), 2),
            },
        }
        
        # Key numeric insights
        if numeric_cols:
            numeric_insights = []
            for col in numeric_cols[:5]:
                data = df[col].dropna()
                if len(data) > 0:
                    numeric_insights.append({
                        "column": col,
                        "mean": round(float(data.mean()), 2),
                        "range": f"{round(float(data.min()), 2)} to {round(float(data.max()), 2)}",
                    })
            insights["key_numeric_columns"] = numeric_insights
        
        insights["plain_english"] = (
            f"This dataset contains {len(df):,} rows and {len(df.columns)} columns. "
            f"Of these, {len(numeric_cols)} columns contain numbers that can be analyzed statistically. "
            f"Overall data quality: {insights['data_quality']['complete_rows_percentage']}% of rows have no missing values. "
        )
        
        return insights
    
    # Helper methods
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
    
    def _interpret_correlation(self, corr: float) -> str:
        """Interpret correlation strength."""
        abs_corr = abs(corr)
        if abs_corr >= 0.8:
            return "very strong"
        elif abs_corr >= 0.6:
            return "strong"
        elif abs_corr >= 0.4:
            return "moderate"
        elif abs_corr >= 0.2:
            return "weak"
        else:
            return "very weak"
    
    def _interpret_skewness(self, skew: float) -> str:
        """Interpret skewness value."""
        if skew > 1:
            return "highly right-skewed (long tail on right)"
        elif skew > 0.5:
            return "moderately right-skewed"
        elif skew > -0.5:
            return "approximately symmetric"
        elif skew > -1:
            return "moderately left-skewed"
        else:
            return "highly left-skewed (long tail on left)"
    
    def _interpret_kurtosis(self, kurt: float) -> str:
        """Interpret kurtosis value."""
        if kurt > 1:
            return "heavy tails (more outliers than normal distribution)"
        elif kurt > -1:
            return "approximately normal tails"
        else:
            return "light tails (fewer outliers than normal distribution)"
    
    def _generate_correlation_interpretation(self, correlations: List[Dict]) -> str:
        """Generate plain English interpretation of correlations."""
        if not correlations:
            return "No significant correlations found."
        
        strongest = correlations[0]
        interpretation = f"The strongest correlation is between {strongest['column_1']} and {strongest['column_2']} "
        interpretation += f"with a {strongest['strength']} {strongest['direction']} correlation of {strongest['correlation']}. "
        
        if len(correlations) > 1:
            interpretation += "Other notable correlations: "
            for c in correlations[1:3]:
                interpretation += f"{c['column_1']}-{c['column_2']} ({c['correlation']}), "
        
        return interpretation.rstrip(", ") + "."
    
    def _generate_single_correlation_interpretation(
        self, col1: str, col2: str, corr: float, p_value: float, n: int
    ) -> str:
        """Generate interpretation for a single correlation."""
        strength = self._interpret_correlation(corr)
        direction = "positive" if corr > 0 else "negative"
        significant = "statistically significant" if p_value < 0.05 else "not statistically significant"
        
        interpretation = (
            f"The correlation between {col1} and {col2} is {corr:.4f}, indicating a {strength} {direction} relationship. "
            f"This result is {significant} (p-value: {p_value:.6f}) based on {n:,} data points. "
        )
        
        if corr > 0:
            interpretation += f"As {col1} increases, {col2} tends to increase as well."
        else:
            interpretation += f"As {col1} increases, {col2} tends to decrease."
        
        return interpretation
    
    def _generate_distribution_interpretation(
        self, stats: Dict, shape: Dict, quartiles: Dict
    ) -> str:
        """Generate distribution interpretation."""
        interpretation = (
            f"The data has an average of {stats['mean']:,.2f} and a median of {stats['median']:,.2f}. "
            f"Values range from {stats['min']:,.2f} to {stats['max']:,.2f}. "
            f"The distribution is {shape['skewness_interpretation']} with {shape['kurtosis_interpretation']}. "
            f"The middle 50% of values fall between {quartiles['q1']:,.2f} and {quartiles['q3']:,.2f} (IQR: {quartiles['iqr']:,.2f})."
        )
        return interpretation
    
    def _generate_outlier_interpretation(self, results: Dict) -> str:
        """Generate outlier interpretation."""
        total_outliers = 0
        columns_with_outliers = []
        
        for col, data in results.items():
            if "iqr_method" in data and data["iqr_method"]["outlier_count"] > 0:
                total_outliers += data["iqr_method"]["outlier_count"]
                columns_with_outliers.append(col)
        
        if total_outliers == 0:
            return "No significant outliers were detected in the analyzed columns."
        
        return (
            f"Found {total_outliers} outliers across {len(columns_with_outliers)} column(s): "
            f"{', '.join(columns_with_outliers)}. "
            f"Outliers are values that fall outside the typical range and may warrant investigation."
        )
    
    def _generate_comparative_interpretation(self, group_stats: List[Dict], value_col: str) -> str:
        """Generate comparative statistics interpretation."""
        if not group_stats:
            return "No groups found for comparison."
        
        top = group_stats[0]
        bottom = group_stats[-1]
        
        interpretation = (
            f"Comparing {value_col} across {len(group_stats)} groups: "
            f"The highest average is '{top['group']}' with {top['mean']:,.2f}, "
            f"while the lowest is '{bottom['group']}' with {bottom['mean']:,.2f}. "
            f"The difference between highest and lowest is {top['mean'] - bottom['mean']:,.2f}."
        )
        
        return interpretation
    
    def _generate_full_summary_interpretation(self, summary: Dict) -> str:
        """Generate full summary interpretation."""
        overview = summary["dataset_overview"]
        
        interpretation = (
            f"Dataset Overview: {overview['total_rows']:,} rows and {overview['total_columns']} columns. "
            f"Contains {overview['numeric_columns']} numeric and {overview['categorical_columns']} categorical columns. "
            f"Data completeness: {100 - overview['missing_percentage']:.1f}% ({overview['missing_percentage']:.1f}% missing values)."
        )
        
        return interpretation


def create_stats_tool(chat_id: str) -> StatsTool:
    """Factory function to create a StatsTool."""
    return StatsTool(chat_id)
