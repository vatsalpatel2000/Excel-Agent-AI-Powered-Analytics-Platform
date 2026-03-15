# 📊 Excel Agent — AI-Powered Analytics Platform

An intelligent, production-grade conversational agent that lets you analyze Excel and CSV files using plain English. Upload a spreadsheet, ask questions, and get instant insights — no formulas, no code, no SQL.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1-412991?logo=openai&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)

---

## ✨ What It Does

> "Show me top 5 products by revenue last quarter" → Instant table + insight

- **Upload** any `.xlsx`, `.xls`, or `.csv` file (multi-sheet supported)
- **Ask** questions in plain English — no need to know formulas or code
- **Get** accurate, deterministic answers powered by Pandas under the hood
- **Export** results as CSV for further use

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                 │
│         Chat UI · File Upload · Markdown Render       │
└──────────────────────┬───────────────────────────────┘
                       │ REST API
┌──────────────────────▼───────────────────────────────┐
│                   Backend (FastAPI)                    │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Ingestion   │  │    Agent     │  │   Memory    │ │
│  │  Pipeline    │  │ Orchestrator │  │  Manager    │ │
│  │             │  │  (GPT-4.1)   │  │             │ │
│  └──────┬──────┘  └──────┬───────┘  └─────────────┘ │
│         │                │                            │
│  ┌──────▼──────────────▼─────────────────────────┐  │
│  │              Tool Layer (6 Tools)               │  │
│  │  metadata · pandas · stats · enrichment ·       │  │
│  │  verification · export                          │  │
│  └─────────────────────┬─────────────────────────┘  │
│                        │                              │
│  ┌─────────────────────▼─────────────────────────┐  │
│  │           Core Engine                           │  │
│  │  DataFrame Registry · Sheet Index ·             │  │
│  │  Execution Guard (sandboxed Pandas)             │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

---

## 🔑 Key Design Principles

| Principle | Description |
|---|---|
| **LLM Never Touches Data** | GPT-4.1 acts as an orchestrator/planner only — all calculations are deterministic via Pandas |
| **Metadata-First Context** | The LLM reasons over column names, types, and statistics — not raw data |
| **Tool-Based Architecture** | 6 specialized tools with strict contracts via OpenAI function calling |
| **Sandboxed Execution** | All generated code runs inside an execution guard with whitelisted operations |
| **Session Memory** | Full conversation context maintained across turns for multi-step analysis |

---

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI + Uvicorn
- **AI:** OpenAI GPT-4.1 (Azure-compatible) with structured function calling
- **Data Engine:** Pandas + NumPy + SciPy
- **File Support:** openpyxl (`.xlsx`), xlrd (`.xls`), native CSV
- **Session Storage:** File-based (Redis-ready for production)

### Frontend
- **Framework:** Next.js 16 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS 4
- **Rendering:** react-markdown + remark-gfm (tables, code blocks)
- **File Upload:** react-dropzone (drag & drop)

### Infrastructure
- **Containerization:** Docker Compose (PostgreSQL + Redis)
- **API Design:** RESTful with streaming support

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- An OpenAI API key (or Azure OpenAI endpoint)

### 1. Clone & Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start the backend
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Setup Frontend

```bash
cd frontend
npm install

# Start the frontend
npm run dev
```

### 3. Open the App

Navigate to [http://localhost:3000](http://localhost:3000), upload a spreadsheet, and start asking questions!

### Docker (Optional)

```bash
# Start PostgreSQL + Redis infrastructure
docker-compose up -d
```

---

## 📂 Project Structure

```
excelagent/
├── backend/
│   ├── app/
│   │   ├── agent/          # AI orchestrator + system prompts
│   │   ├── api/            # FastAPI routes (chat, files, export)
│   │   ├── core/           # DataFrame registry, sheet index, execution guard
│   │   ├── ingestion/      # Excel/CSV parser, schema normalizer, table detector
│   │   ├── memory/         # Session state + chat memory
│   │   ├── tools/          # 6 agent tools (metadata, pandas, stats, etc.)
│   │   └── main.py         # Application entry point
│   ├── tests/              # Pytest test suite
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js pages + layouts
│   │   ├── components/     # React components (ChatWindow, FileUpload, etc.)
│   │   └── lib/            # API client + TypeScript types
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml      # PostgreSQL + Redis for local dev
└── README.md
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/message` | Send a message to the agent |
| `GET` | `/api/chat/history/{chat_id}` | Get conversation history |
| `GET` | `/api/chat/context/{chat_id}` | Get current data context |
| `POST` | `/api/files/upload` | Upload an Excel/CSV file |
| `GET` | `/api/files/sheets/{chat_id}` | List all loaded sheets |
| `POST` | `/api/export/csv` | Export analysis results to CSV |

---

## 🧪 Testing

```bash
cd backend
pytest tests/ -v
```

---

## 👤 Author

**Vatsal Patel**

---
