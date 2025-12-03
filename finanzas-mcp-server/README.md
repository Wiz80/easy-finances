# Finanzas MCP Server

MCP (Model Context Protocol) server for the Finanzas Personales application.

Provides NL-to-SQL capabilities using OpenAI + Qdrant for context-aware SQL generation.

## Features

- **NL to SQL**: Convert natural language questions to SQL queries
- **Secure Query Execution**: Read-only SQL execution with user isolation
- **PostgreSQL Resource**: Direct database schema access
- **User-Aware**: All queries filtered by user_id for data isolation

## Tools

| Tool | Description |
|------|-------------|
| `generate_sql` | Convert natural language question to SQL query |
| `run_sql_query` | Execute a validated SQL query (SELECT only) |
| `get_database_schema` | Get database schema information |

## Resources

| Resource | Description |
|----------|-------------|
| `postgres://tables` | List of available tables |
| `postgres://schema/{table}` | DDL for a specific table |

## Project Structure

```
finanzas-mcp-server/
├── src/
│   ├── server.py           # FastMCP server entry point
│   ├── config.py           # Configuration
│   ├── sql_validator.py    # SQL validation (SELECT only)
│   ├── tools/              # MCP tools
│   │   ├── nl_to_sql.py
│   │   ├── execute_sql.py
│   │   └── schema.py
│   └── services/           # Internal services
│       ├── database.py     # PostgreSQL connection
│       ├── embeddings.py   # OpenAI embeddings + Qdrant
│       └── llm.py          # SQL generation with LLM
├── vanna_training/         # Training system
│   ├── config.json         # Training configuration
│   └── train.py            # Training script
└── pyproject.toml
```

## Installation

```bash
cd finanzas-mcp-server
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Configuration

Copy `env.example` to `.env` and configure:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=finanzas_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=finanzas_db

# Read-only user
VANNA_DB_USER=vanna_reader
VANNA_DB_PASSWORD=readonly_password

# OpenAI
OPENAI_API_KEY=sk-...

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

## Training

Before using, train the system with your database schema:

```bash
cd finanzas-mcp-server
python -m vanna_training.train
```

## Usage

### STDIO Mode (Development)

```bash
python -m src.server
```

### SSE Mode (Production)

```bash
python -m src.server --transport sse --port 8080
```

### From Coach Agent

The Coach Agent in the main app connects automatically:

```python
from app.agents.coach_agent import ask_coach

result = await ask_coach(
    user_id="abc-123",
    question="¿Cuánto gasté este mes?"
)
print(result.response)
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Coach Agent (app/agents/coach_agent/)       │
│                    LangGraph + MCP Adapters              │
└─────────────────────────┬───────────────────────────────┘
                          │ STDIO / SSE
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Finanzas MCP Server (this repo)             │
│                                                          │
│  Tools:                                                  │
│  ├── generate_sql (NL → SQL with context from Qdrant)   │
│  ├── run_sql_query (Execute validated SELECT)           │
│  └── get_database_schema (Schema info)                  │
│                                                          │
│  Services:                                               │
│  ├── OpenAI (embeddings + SQL generation)               │
│  ├── Qdrant (DDL, docs, SQL examples)                   │
│  └── PostgreSQL (read-only queries)                     │
└─────────────────────────────────────────────────────────┘
```

## Security

- Only SELECT statements allowed
- All queries must include user_id filter
- Read-only PostgreSQL user
- Query timeout (30s)
- Result limit (1000 rows)
