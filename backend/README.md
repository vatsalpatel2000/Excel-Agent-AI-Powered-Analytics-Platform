# Excel Agent - Unified Backend

A production-grade Excel/CSV analysis agent with AI-powered insights.

## Features

- **Multi-Sheet Support**: Loads ALL sheets from Excel files, not just the first
- **Metadata-First Prompting**: LLM reasons over structure, not raw data
- **Deterministic Execution**: All calculations via Pandas, never LLM
- **Plain English Output**: Responses understandable by anyone
- **Tool-Based Architecture**: Structured function calling with OpenAI
- **Session Memory**: Maintains context across conversation turns
- **Azure-Ready**: Interfaces ready for Redis, Azure SQL, Blob Storage

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=your-key-here

# Run the server
python -m uvicorn app.main:app --reload
```

## API Endpoints

### Chat
- `POST /api/chat/message` - Send a message to the agent
- `GET /api/chat/history/{chat_id}` - Get conversation history
- `GET /api/chat/context/{chat_id}` - Get current data context

### Files
- `POST /api/files/upload` - Upload an Excel/CSV file
- `GET /api/files/sheets/{chat_id}` - List all sheets
- `GET /api/files/sheet/{chat_id}/{sheet_name}` - Get sheet details

### Export
- `POST /api/export/csv` - Export data to CSV
- `GET /api/export/download/{filename}` - Download exported file

## Architecture

```
backend/
├── app/
│   ├── core/           # Core data structures
│   │   ├── dataframe_registry.py  # DataFrame storage
│   │   ├── sheet_index.py         # Metadata graph
│   │   └── execution_guard.py      # Safe code execution
│   ├── ingestion/      # File processing
│   │   ├── excel_parser.py
│   │   ├── schema_normalizer.py
│   │   └── table_detector.py
│   ├── agent/          # AI orchestration
│   │   └── orchestrator.py         # Hybrid agent
│   ├── tools/          # Agent tools
│   │   ├── metadata_tool.py
│   │   ├── pandas_tool.py
│   │   ├── enrichment_tool.py
│   │   └── export_tool.py
│   ├── memory/         # State management
│   │   ├── session_state.py
│   │   └── chat_memory.py
│   └── api/            # FastAPI routes
│       ├── chat.py
│       ├── files.py
│       └── export.py
```

## Key Design Principles

1. **LLM is Never Trusted with Data**
   - LLM acts as orchestrator/planner
   - All data truth lives in Pandas
   - Calculations are deterministic

2. **Metadata-First Context**
   - Send structure, not raw data
   - Column names, types, statistics
   - Sample values for understanding

3. **Tool-First Architecture**
   - Structured function calling
   - Clear tool contracts
   - Predictable execution

## Testing

```bash
pytest tests/ -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| OPENAI_API_KEY | OpenAI API key | Required |
| OPENAI_MODEL | Model to use | gpt-4o |
| MAX_ITERATIONS | Max reasoning iterations | 5 |
| MAX_FILE_SIZE_MB | Max upload size | 50 |
| REDIS_ENABLED | Enable Redis caching | false |
