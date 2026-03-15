"""
Hybrid Agent Orchestrator - Production Grade

Combines the best of both approaches:
1. OpenAI Function Calling for structured tool use
2. Code Interpreter fallback for complex queries
3. Iterative reasoning loop (up to MAX_ITERATIONS)
4. Metadata-first prompting (never sends raw data)
5. Plain English response synthesis

This is the BRAIN of the Excel Agent.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from openai import AsyncOpenAI

from app.config import settings
from app.core import get_dataframe_registry, get_sheet_index, get_execution_guard
from app.tools import (
    create_metadata_tool,
    create_pandas_tool,
    create_enrichment_tool,
    create_export_tool,
    create_stats_tool,
    create_verification_tool,
)

logger = logging.getLogger(__name__)

# Load system prompt
PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT = (PROMPTS_DIR / "system.txt").read_text()


class QueryIntent(Enum):
    """Detected intent of user query."""
    SUMMARY = "summary"
    ANALYSIS = "analysis"
    STATISTICS = "statistics"  # Deep statistical analysis
    FILTER = "filter"
    ENRICHMENT = "enrichment"
    CSV_OUTPUT = "csv_output"
    COMPARISON = "comparison"
    GREETING = "greeting"
    UNKNOWN = "unknown"


# OpenAI Function/Tool Definitions
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "metadata_tool",
            "description": "Query information about available data - sheets, columns, statistics. Use this first to understand what data exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list_sheets", "get_sheet_info", "get_column_stats", "get_sample_rows", "search_columns"],
                        "description": "The action to perform"
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet to query (use exact name from list_sheets)"
                    },
                    "column_name": {
                        "type": "string",
                        "description": "Column name for column-specific actions"
                    },
                    "n": {
                        "type": "integer",
                        "description": "Number of sample rows to return (default: 5)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pandas_tool",
            "description": "Perform data analysis operations like filtering, grouping, aggregating, and computing statistics. All calculations MUST use this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["filter", "select", "groupby", "sort", "describe", "value_counts", "head", "tail", "count", "sum", "mean", "unique", "query", "code"],
                        "description": "The operation to perform. Use 'code' for complex custom operations."
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet to operate on"
                    },
                    "column": {
                        "type": "string",
                        "description": "Column name for single-column operations"
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of columns for multi-column operations"
                    },
                    "conditions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {"type": "string", "enum": ["==", "!=", ">", ">=", "<", "<=", "contains", "isnull", "notnull"]},
                                "value": {}
                            }
                        },
                        "description": "Filter conditions"
                    },
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to group by"
                    },
                    "aggregations": {
                        "type": "object",
                        "description": "Aggregations to apply: {column: 'sum'|'mean'|'count'|'min'|'max'}"
                    },
                    "by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to sort by"
                    },
                    "ascending": {
                        "type": "boolean",
                        "description": "Sort ascending (default: true)"
                    },
                    "n": {
                        "type": "integer",
                        "description": "Number of rows for head/tail"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Top N for value_counts"
                    },
                    "expression": {
                        "type": "string",
                        "description": "Query expression for 'query' operation"
                    },
                    "code": {
                        "type": "string",
                        "description": "Python/Pandas code for 'code' operation. Must set result variable."
                    }
                },
                "required": ["operation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enrichment_tool",
            "description": "Enrich company data with sector and industry classifications.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["classify_companies", "classify_single", "preview_enrichment"],
                        "description": "The action to perform"
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet containing company data"
                    },
                    "company_column": {
                        "type": "string",
                        "description": "Name of the column containing company names"
                    },
                    "company_name": {
                        "type": "string",
                        "description": "Single company name to classify (for classify_single)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "export_tool",
            "description": "Export data to downloadable CSV or Excel files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["export_csv", "export_enriched", "export_with_introduction"],
                        "description": "The action to perform"
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet to export"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Custom filename for the export"
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to export (optional, exports all if not specified)"
                    },
                    "limit_rows": {
                        "type": "integer",
                        "description": "Limit the number of rows to export (e.g., top 20)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stats_tool",
            "description": "Advanced statistical analysis: correlations, distributions, outliers, percentiles, trend analysis. Use for deep analytical questions requiring statistical insights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "correlation_matrix",
                            "correlation",
                            "distribution_analysis",
                            "outlier_detection",
                            "percentile_analysis",
                            "comparative_stats",
                            "trend_analysis",
                            "summary_insights",
                            "full_statistical_summary"
                        ],
                        "description": "The statistical analysis to perform"
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet to analyze"
                    },
                    "column": {
                        "type": "string",
                        "description": "Column for single-column analysis"
                    },
                    "column_1": {
                        "type": "string",
                        "description": "First column for correlation analysis"
                    },
                    "column_2": {
                        "type": "string",
                        "description": "Second column for correlation analysis"
                    },
                    "group_column": {
                        "type": "string",
                        "description": "Column to group by for comparative_stats"
                    },
                    "value_column": {
                        "type": "string",
                        "description": "Numeric column to analyze for comparative_stats"
                    },
                    "percentiles": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of percentiles to calculate (e.g., [10, 25, 50, 75, 90])"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["iqr", "zscore", "both"],
                        "description": "Outlier detection method"
                    }
                },
                "required": ["operation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verification_tool",
            "description": "CRITICAL: Use this tool FIRST for any numerical calculation. Performs dual verification (direct calculation vs total-minus-inverse) to ensure 100% accuracy. Always verify before reporting numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "verified_sum",
                            "verified_mean",
                            "verified_count",
                            "verified_filter_aggregate",
                            "full_verification"
                        ],
                        "description": "The verification operation. Use verified_filter_aggregate for most calculations."
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet"
                    },
                    "value_column": {
                        "type": "string",
                        "description": "Column containing numeric values to aggregate"
                    },
                    "filter_column": {
                        "type": "string",
                        "description": "Column to filter on"
                    },
                    "filter_value": {
                        "type": "string",
                        "description": "Value to match in filter column"
                    },
                    "aggregation": {
                        "type": "string",
                        "enum": ["sum", "mean", "count", "min", "max"],
                        "description": "Type of aggregation to perform"
                    }
                },
                "required": ["operation"]
            }
        }
    }
]


@dataclass
class AgentState:
    """State for agent reasoning loop."""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls_made: int = 0
    max_iterations: int = field(default_factory=lambda: settings.MAX_ITERATIONS)
    final_answer: Optional[str] = None
    error: Optional[str] = None
    csv_generated: bool = False
    csv_path: Optional[str] = None


class HybridOrchestrator:
    """
    Production-Grade Hybrid Agent Orchestrator.
    
    Key features:
    - OpenAI Function Calling for structured operations
    - Code Interpreter fallback for complex queries
    - Iterative reasoning loop
    - Metadata-first context
    - Plain English synthesis
    """
    
    # Intent detection patterns
    SUMMARY_PATTERNS = [r'\bsummar', r'\bdescribe\b', r'\boverview\b', r'\bexplain\b', r'\btell me about\b', r'\bwhat.*in\b']
    # CSV only when user explicitly asks for download/export/file - NOT when just mentioning "excel" 
    CSV_PATTERNS = [r'\bcsv\b', r'\bexport\b', r'\bdownload\b', r'\bsave\b', r'\bgenerate.*file\b', r'\bgive me.*file\b', r'\bgive me.*excel\b', r'\bgive me.*csv\b', r'\bnew.*excel\b', r'\bcreate.*file\b']
    INTRODUCTION_PATTERNS = [r'\bintroduction\b', r'\bintro\b']
    ENRICHMENT_PATTERNS = [r'\badd.*sector\b', r'\badd.*industry\b', r'\benrich\b', r'\bclassify.*compan']
    COMPARISON_PATTERNS = [r'\bcompare\b', r'\bvs\b', r'\bdifference\b']
    GREETING_PATTERNS = [r'^hi\b', r'^hello\b', r'^hey\b', r'^good\s*(morning|evening|afternoon)']
    # Statistical analysis patterns - triggers deep statistical analysis
    STATISTICS_PATTERNS = [
        r'\bcorrelat', r'\bdistribut', r'\boutlier', r'\bpercentile', r'\bquartile',
        r'\bstandard\s*deviation', r'\bstd\b', r'\bvariance\b', r'\bskew', r'\bkurtosis',
        r'\btrend\b', r'\bstatistic', r'\bnormal\s*distribut', r'\bregression',
        r'\bp-value', r'\bsignifican', r'\bconfidence\s*interval', r'\bhypothesis'
    ]
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        # Only pass base_url if it's actually configured
        client_kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL
        self.client = AsyncOpenAI(**client_kwargs)

        
        # Core services
        self.df_registry = get_dataframe_registry()
        self.sheet_index = get_sheet_index()
        self.execution_guard = get_execution_guard()
        
        # Initialize tools
        self.tools = {
            "metadata_tool": create_metadata_tool(chat_id),
            "pandas_tool": create_pandas_tool(chat_id),
            "enrichment_tool": create_enrichment_tool(chat_id),
            "export_tool": create_export_tool(chat_id),
            "stats_tool": create_stats_tool(chat_id),
            "verification_tool": create_verification_tool(chat_id),
        }
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Process a user message and return a response.
        
        This is the main entry point for the agent.
        """
        # Classify intent
        intent = self._classify_intent(user_message)
        
        # Handle greetings specially
        if intent == QueryIntent.GREETING:
            return self._handle_greeting()
        
        # Check if data is loaded
        sheet_count = self.sheet_index.get_sheet_count(self.chat_id)
        if sheet_count == 0:
            return self._no_data_response()
        
        # Detect if this is a CSV/export request
        is_csv_request = intent == QueryIntent.CSV_OUTPUT
        
        # Build agent state
        state = AgentState()
        
        # Use compact context for large datasets to avoid token limits
        total_rows = sum(s.row_count for s in self.sheet_index.get_all(self.chat_id))
        if total_rows > 1000:
            data_context = self.sheet_index.build_compact_context(self.chat_id)
        else:
            data_context = self.sheet_index.build_context_for_llm(self.chat_id, include_samples=True, max_columns=10)
        
        # Build system prompt with emphasis on CSV if needed
        system_prompt = self._build_system_prompt(data_context, is_csv_request)
        
        state.messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Add conversation history (limit to avoid token overflow)
        if conversation_history:
            # Only keep last 3 messages to save tokens
            for msg in conversation_history[-3:]:
                content = msg.get("content", "")
                # Truncate long messages
                if len(content) > 500:
                    content = content[:500] + "..."
                state.messages.append({
                    "role": msg.get("role", "user"),
                    "content": content,
                })
        
        # Add current user message
        state.messages.append({"role": "user", "content": user_message})
        
        # For CSV requests, add hint to use export_tool
        if is_csv_request:
            # Check if user wants introduction column
            wants_introduction = any(re.search(p, user_message.lower()) for p in self.INTRODUCTION_PATTERNS)
            
            if wants_introduction:
                state.messages.append({
                    "role": "system",
                    "content": """IMPORTANT: User wants a downloadable file WITH an Introduction column.
You MUST use the export_tool with action='export_with_introduction' to generate a CSV with the Introduction column.
If user specifies a row limit (e.g., 'first 50 rows'), pass that as limit_rows parameter.
Example: export_tool(action="export_with_introduction", limit_rows=50, filename="data_with_intro")"""
                })
            else:
                state.messages.append({
                    "role": "system",
                    "content": "IMPORTANT: User wants a downloadable file. You MUST use the export_tool with action='export_csv' to generate a downloadable CSV."
                })
        
        # Run agentic loop
        try:
            response = await self._reasoning_loop(state)
            return self._ensure_plain_english(response)
        except Exception as e:
            logger.exception(f"Agent error: {e}")
            return f"I encountered an error while processing your request: {str(e)}. Please try rephrasing your question."
    
    def _classify_intent(self, message: str) -> QueryIntent:
        """Classify user intent from message."""
        msg_lower = message.lower().strip()
        
        for pattern in self.GREETING_PATTERNS:
            if re.search(pattern, msg_lower):
                return QueryIntent.GREETING
        
        for pattern in self.CSV_PATTERNS:
            if re.search(pattern, msg_lower):
                return QueryIntent.CSV_OUTPUT
        
        for pattern in self.ENRICHMENT_PATTERNS:
            if re.search(pattern, msg_lower):
                return QueryIntent.ENRICHMENT
        
        # Check for statistical analysis intent
        for pattern in self.STATISTICS_PATTERNS:
            if re.search(pattern, msg_lower):
                return QueryIntent.STATISTICS
        
        for pattern in self.COMPARISON_PATTERNS:
            if re.search(pattern, msg_lower):
                return QueryIntent.COMPARISON
        
        for pattern in self.SUMMARY_PATTERNS:
            if re.search(pattern, msg_lower):
                return QueryIntent.SUMMARY
        
        return QueryIntent.ANALYSIS
    
    def _build_system_prompt(self, data_context: str, is_csv_request: bool = False) -> str:
        """Build system prompt with current data context."""
        csv_instruction = ""
        if is_csv_request:
            csv_instruction = """
## IMPORTANT: CSV Export Request
The user wants to download data as a file. You MUST:
1. Use the export_tool with action="export_csv" 
2. Specify the sheet_name to export
3. Provide a clear download link in your response
"""
        
        return f"""{SYSTEM_PROMPT}
{csv_instruction}
## Currently Available Data

{data_context}
"""
    
    def _handle_greeting(self) -> str:
        """Handle greeting messages."""
        sheets = self.sheet_index.get_all(self.chat_id)
        
        if sheets:
            total_rows = sum(s.row_count for s in sheets)
            sheet_info = []
            for s in sheets:
                cols_preview = ", ".join(list(s.columns.keys())[:4])
                if len(s.columns) > 4:
                    cols_preview += f" (+{len(s.columns) - 4} more)"
                sheet_info.append(f"  - **{s.sheet_name}**: {s.row_count:,} rows ({cols_preview})")
            
            return f"""Hello! 👋 I'm your Excel Analysis Assistant.

I see you have data loaded with **{len(sheets)} sheet(s)** and **{total_rows:,} total rows**:

{chr(10).join(sheet_info)}

I can help you:
- **Analyze data**: "What's the average revenue by sector?"
- **Filter and search**: "Show me rows where Country is USA"
- **Compare sheets**: "Compare Sheet 1 and Sheet 2"
- **Enrich data**: "Add sector and industry columns"
- **Export results**: "Download as CSV"

What would you like to know about your data?"""
        
        return """Hello! 👋 I'm your Excel Analysis Assistant.

Please upload an Excel or CSV file to get started. I can:
- Answer any question about your data
- Perform calculations and analysis
- Add sector/industry classifications
- Export results as CSV

**Supported formats:** .xlsx, .xls, .xlsm, .csv"""
    
    def _no_data_response(self) -> str:
        """Response when no data is loaded."""
        return """⚠️ **No data loaded yet**

Please upload an Excel or CSV file first to start analyzing.

**Supported formats:** `.xlsx`, `.xls`, `.xlsm`, `.csv`

Once uploaded, I can answer any question about your data!"""
    
    async def _reasoning_loop(self, state: AgentState) -> str:
        """
        The agentic reasoning loop.
        
        Continues until:
        - Agent produces final answer without tool calls
        - Max iterations reached
        - Error occurs
        """
        while state.tool_calls_made < state.max_iterations * 3:  # Allow multiple tool calls per iteration
            try:
                response = await self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=state.messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=settings.TEMPERATURE,
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                )
                
                message = response.choices[0].message
                
                # Check if we have tool calls
                if message.tool_calls:
                    # Add assistant message with tool calls
                    state.messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })
                    
                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        result = await self._execute_tool(
                            tool_call.function.name,
                            tool_call.function.arguments,
                        )
                        
                        state.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result, default=str, ensure_ascii=False)
                        })
                        
                        state.tool_calls_made += 1
                        
                        # Check for CSV export
                        if tool_call.function.name == "export_tool" and result.get("success"):
                            state.csv_generated = True
                            state.csv_path = result.get("download_url")
                    
                    logger.info(f"Made {state.tool_calls_made} tool calls so far")
                else:
                    # No tool calls - this is the final answer
                    final_response = message.content or "I couldn't generate a response."
                    
                    # Append CSV download if generated
                    if state.csv_generated and state.csv_path:
                        final_response += f"\n\n📥 **Download**: [Click here to download]({state.csv_path})"
                    
                    return final_response
                    
            except Exception as e:
                logger.exception(f"Error in reasoning loop: {e}")
                return f"I encountered an error: {str(e)}"
        
        # Max iterations reached
        return "I made multiple attempts to analyze your data but couldn't complete the request. Please try breaking down your question into smaller parts."
    
    async def _execute_tool(self, tool_name: str, arguments: str) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON arguments: {arguments}"}
        
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}
        
        tool = self.tools[tool_name]
        
        logger.info(f"Executing {tool_name} with args: {args}")
        
        try:
            # Different tools have different signatures
            if tool_name == "metadata_tool":
                action = args.pop("action", "list_sheets")
                return tool.execute(action, args)
            elif tool_name == "pandas_tool":
                operation = args.pop("operation", "describe")
                return tool.execute(operation, args)
            elif tool_name == "enrichment_tool":
                action = args.pop("action", "classify_companies")
                return await tool.execute(action, args)
            elif tool_name == "export_tool":
                action = args.pop("action", "export_csv")
                return tool.execute(action, args)
            elif tool_name == "stats_tool":
                operation = args.pop("operation", "full_statistical_summary")
                return tool.execute(operation, args)
            elif tool_name == "verification_tool":
                operation = args.pop("operation", "verified_filter_aggregate")
                return tool.execute(operation, args)
            else:
                return {"error": f"Tool {tool_name} not implemented"}
        except Exception as e:
            logger.exception(f"Tool execution error: {e}")
            return {"error": str(e)}
    
    def _ensure_plain_english(self, text: str) -> str:
        """
        Final pass to remove any technical content that leaked through.
        """
        # Remove DataFrame-like patterns
        text = re.sub(r'\{[^{}]*\}', '', text)  # Remove dict literals
        text = re.sub(r'Timestamp\([^)]*\)', '(date)', text)
        text = re.sub(r'dtype:?\s*\w+', '', text)
        text = re.sub(r'\bNaN\b', 'missing', text, flags=re.IGNORECASE)
        text = re.sub(r'df\[', 'the ', text)
        text = re.sub(r'\.\w+\(\d*\)', '', text)  # Remove method calls like .head()
        
        # Clean up multiple empty lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()


async def process_chat_message(
    chat_id: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Process a chat message and return the response.
    
    This is the main API for the orchestrator.
    """
    orchestrator = HybridOrchestrator(chat_id)
    return await orchestrator.process_message(message, history)
