# Phase 1 — IE Agent & Expense Storage (MVP)

> **Status**: Planning  
> **Start Date**: 2025-11-11  
> **Target Timeline**: 2-3 weeks  
> **Owner**: Development Team

## 1) Overview

This phase focuses on building the **Information Extraction (IE) Agent** and the foundational expense storage layer. The goal is to process multi-modal inputs (text, voice, images, documents) and persist structured expense records into PostgreSQL.

**Key Deliverables**:
- Multi-modal extraction tools (text, audio, image/receipt parsing)
- Expense storage layer with PostgreSQL schema
- LangGraph orchestrated agent for routing and execution
- Basic validation and confidence scoring

## 2) Objectives

1. **Input Processing**: Accept text, voice notes, images, and document receipts
2. **Information Extraction**: Parse and normalize expense data from any input type
3. **Expense Storage**: Persist structured expense records to PostgreSQL
4. **Agent Orchestration**: Use LangGraph to coordinate extraction → validation → storage
5. **Idempotency**: Ensure duplicate detection via message IDs and content hashes

## 3) Architecture Components

```
┌─────────────────────────────────────────────────────────┐
│                     IE Agent (LangGraph)                 │
│                                                          │
│  ┌─────────────┐      ┌──────────────────────────┐    │
│  │   Router    │─────▶│  Extraction Tools Layer  │    │
│  │  (Intent)   │      │                          │    │
│  └─────────────┘      │  • Text Extractor        │    │
│                       │  • Audio Transcriber     │    │
│                       │  • Image Parser (OCR)    │    │
│                       │  • Receipt Parser        │    │
│                       └──────────────────────────┘    │
│                                                          │
│                       ┌──────────────────────────┐    │
│                       │   Normalizer & Validator │    │
│                       └──────────────────────────┘    │
│                                                          │
│                       ┌──────────────────────────┐    │
│                       │    Storage Layer         │    │
│                       │  • Expense Writer        │    │
│                       │  • Receipt Metadata      │    │
│                       └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                              ▼
                     ┌──────────────────┐
                     │   PostgreSQL     │
                     │   • expenses     │
                     │   • receipts     │
                     └──────────────────┘
```

## 4) Development Plan

### 4.1) Phase 1A — Foundation & Schema

**Tasks**:
1. **Database Schema Design**
   - Define `expense` table with core fields:
     - `id`, `user_id`, `account_id`, `trip_id`, `category_id`
     - `amount_original`, `currency_original`
     - `occurred_at`, `description`, `merchant`
     - `method` (cash/card), `card_id` (nullable)
     - `status` (pending_confirm, confirmed, flagged)
     - `confidence_score`, `source_type`, `source_meta` (JSONB)
     - Timestamps: `created_at`, `updated_at`
   
   - Define `receipt` table:
     - `id`, `expense_id` (FK), `blob_uri`, `content_hash`
     - `parse_status`, `parsed_data` (JSONB)
     - `ocr_provider`, `ocr_confidence`
     - Timestamps

   - Define supporting tables (minimal for MVP):
     - `user`, `account`, `trip`, `category`, `card`

2. **Alembic Setup**
   - Initialize Alembic for migrations
   - Create initial migration with schema

3. **SQLAlchemy Models**
   - Define ORM models for all tables
   - Set up relationships and indexes

**Deliverables**:
- `alembic/versions/001_initial_schema.py`
- `app/models/` with SQLAlchemy models
- Database seeded with test categories (FOOD, LODGING, TRANSPORT, TOURISM, MISC)

**Estimated Time**: 2-3 days

---

### 4.2) Phase 1B — Extraction Tools Layer

Build standalone extraction functions/classes for each input type.

#### **Tool 1: Text Extractor**

**Purpose**: Parse structured expense data from plain text messages.

**Implementation**:
```
Module: app/tools/extraction/text_extractor.py

Input: str (e.g., "20 soles groceries cash")
Output: ExtractedExpense(
    amount: Decimal,
    currency: str,
    description: str,
    category_candidate: str,
    method: str,
    confidence: float,
    raw_input: str
)

Approach:
- Use LLM via LangChain with structured output (Pydantic schema)
- **Default Provider**: OpenAI (GPT-4o)
- **Configurable**: Support for Anthropic Claude, Google Gemini
- Prompt engineering for currency, amount, category detection
- Confidence scoring based on field completeness and ambiguity

Configuration:
- Use OPENAI_API_KEY (default provider)
- Prompts stored in app/prompts/ directory
- Future: Migrate to Langfuse for prompt management and versioning
```

**Dependencies**:
- LangChain Core
- LangChain-OpenAI (default)
- Optional: LangChain-Anthropic, LangChain-Google-GenAI
- Pydantic schemas for structured output

---

#### **Tool 2: Audio Transcriber**

**Purpose**: Convert voice notes to text, then extract expense data.

**Implementation**:
```
Module: app/tools/extraction/audio_extractor.py

Input: bytes (audio file) or file path
Output: ExtractedExpense (same as text)

Pipeline:
1. Speech-to-Text using OpenAI Whisper API (default)
   - Fallback: faster-whisper (local open-source option)
2. Pass transcription to Text Extractor
3. Store original audio reference and transcript in source_meta

Confidence:
- Factor in ASR confidence + text extraction confidence

Configuration:
- Use OPENAI_API_KEY for Whisper API access
- Optional: faster-whisper for local processing (heavier but offline)
```

**Dependencies**:
- OpenAI Python SDK (for Whisper API)
- faster-whisper (optional, local fallback)
- ffmpeg for audio preprocessing if needed

**Note**: Default to OpenAI Whisper API to avoid heavy model downloads. Local Whisper option available for offline scenarios.

---

#### **Tool 3: Image/Receipt Parser**

**Purpose**: Extract structured data from receipt images and PDFs via intelligent OCR.

**Implementation**:
```
Module: app/tools/extraction/receipt_parser.py

Input: bytes (image/PDF) or file path
Output: ExtractedReceipt(
    merchant: str,
    total_amount: Decimal,
    currency: str,
    line_items: List[LineItem],
    occurred_at: datetime,
    confidence: float,
    raw_text: str,
    raw_markdown: str  # LlamaParse markdown output
)

Approach:
- **Primary**: Use LlamaParse for structured extraction
  - Supports images (JPG, PNG) and PDFs
  - Output formats: Markdown (.md) for general text, JSON for tables
  - Excellent for invoices, receipts, and transaction records
  
Pipeline:
1. Upload document to LlamaParse service via API
2. Get structured response (markdown + JSON for tables)
3. Parse and extract: merchant, amounts, currency, line items, dates
4. Normalize currency codes (ISO 4217), dates (ISO 8601), amounts
5. Compute content hash (SHA256) for deduplication
6. Map extracted data to ExtractedReceipt schema

Configuration:
- Use LLAMAPARSE_API_KEY for API access
- Configure output format (markdown + JSON for tables)
- Set parsing mode: "precise" for receipts/invoices
```

**Dependencies**:
- llama-parse SDK (LlamaIndex)
- Pillow for image preprocessing/validation
- hashlib for content hashing
- python-dateutil for date parsing

**Note**: LlamaParse handles both images and PDFs natively, eliminating need for separate document parser in MVP.

---

#### **Tool 4: Document Parser (Covered by LlamaParse)**

**Purpose**: Handle PDF receipts or multi-page documents.

**Status**: ✅ **Not needed as separate tool** - LlamaParse handles PDFs natively.

**Implementation Note**:
```
LlamaParse (Tool 3) already supports:
- Single and multi-page PDFs
- Mixed content (text, tables, images)
- Direct PDF → Markdown + JSON extraction

No additional tool required for MVP.
```

**Future Enhancement** (Phase 2+):
- If LlamaParse limitations found, consider fallback:
  - PyMuPDF for text-heavy PDFs
  - pdf2image + OCR for scanned documents

---

**Deliverables (Phase 1B)**:
- `app/tools/extraction/` module with all extractors
- `app/schemas/extraction.py` with Pydantic models
- Unit tests for each extractor with sample inputs
- Confidence scoring logic documented

**Estimated Time**: 4-5 days

---

### 4.3) Phase 1C — Storage Layer

Build functions to persist extracted data to PostgreSQL.

#### **Storage 1: Expense Writer**

**Implementation**:
```
Module: app/storage/expense_writer.py

Function: create_expense(
    extracted: ExtractedExpense,
    user_id: UUID,
    account_id: UUID,
    trip_id: UUID | None,
    card_id: UUID | None,
    session: Session
) -> Expense

Logic:
1. Check for duplicate via source_meta (msg_id or content hash)
2. Map category_candidate to category_id (lookup or ML classifier)
3. Insert expense with status=pending_confirm
4. Return created Expense ORM object

Idempotency:
- Query by source_meta.msg_id or hash
- Return existing record if found (409 or success response)
```

---

#### **Storage 2: Receipt Writer**

**Implementation**:
```
Module: app/storage/receipt_writer.py

Function: create_receipt(
    expense_id: UUID,
    image_bytes: bytes,
    parsed_data: ExtractedReceipt,
    session: Session
) -> Receipt

Logic:
1. Compute content_hash (SHA256 of image bytes)
2. Check for duplicate by hash
3. Upload image to object storage (MinIO or local filesystem for MVP)
4. Store blob_uri, parsed_data (JSONB), ocr_confidence
5. Link to expense via expense_id FK
```

**Dependencies**:
- Object storage client (MinIO Python SDK or boto3)
- hashlib

---

**Deliverables (Phase 1C)**:
- `app/storage/` module with expense and receipt writers
- Idempotency checks implemented
- Integration tests with test database

**Estimated Time**: 2-3 days

---

### 4.4) Phase 1D — LangGraph Agent Orchestration

Build the IE Agent using LangGraph to coordinate extraction and storage.

#### **Agent Architecture**

```python
# Conceptual structure

from langgraph.graph import StateGraph, END

class IEAgentState(TypedDict):
    input_type: str  # "text" | "audio" | "image" | "document"
    raw_input: Any   # bytes, str, or file path
    user_id: UUID
    account_id: UUID
    trip_id: UUID | None
    
    # Intermediate state
    extracted_data: ExtractedExpense | ExtractedReceipt | None
    confidence: float
    errors: List[str]
    
    # Output
    expense_id: UUID | None
    receipt_id: UUID | None
    status: str

# Nodes:
# 1. router_node: Determine input_type and select extraction tool
# 2. extract_text_node: Use Text Extractor
# 3. extract_audio_node: Use Audio Transcriber
# 4. extract_image_node: Use Image/Receipt Parser
# 5. validate_node: Check confidence threshold, required fields
# 6. store_expense_node: Write to database
# 7. store_receipt_node: Write receipt metadata (if image input)
# 8. error_node: Handle failures, log, return error state

# Edges:
# router → extract_* → validate → store_* → END
# validate → error_node (if confidence too low)
```

#### **Implementation Steps**

1. **Define State Schema**
   - `app/agents/ie_agent/state.py`

2. **Implement Nodes**
   - `app/agents/ie_agent/nodes/router.py`
   - `app/agents/ie_agent/nodes/extractors.py`
   - `app/agents/ie_agent/nodes/validator.py`
   - `app/agents/ie_agent/nodes/storage.py`

3. **Build Graph**
   - `app/agents/ie_agent/graph.py`
   - Connect nodes with conditional edges

4. **Create Entry Point**
   - `app/agents/ie_agent/agent.py` - main invocation function

5. **Logging & Observability**
   - Structured logs at each node with `request_id`, `user_id`, timing
   - LangSmith tracing enabled

---

**Deliverables (Phase 1D)**:
- `app/agents/ie_agent/` complete module
- Integration with extraction tools and storage layer
- End-to-end tests for each input type
- Documentation: architecture diagram and usage examples

**Estimated Time**: 4-5 days

---

### 4.5) Phase 1E — Testing & Validation

**Test Coverage**:

1. **Unit Tests**
   - Each extraction tool with mock/sample inputs
   - Storage functions with test database
   - Idempotency checks

2. **Integration Tests**
   - Full agent execution for each input type
   - Database state validation
   - Error handling scenarios

3. **Manual Smoke Tests**
   - `tests-manual/test_ie_agent_text.py`
   - `tests-manual/test_ie_agent_audio.py`
   - `tests-manual/test_ie_agent_receipt.py`
   - Print summaries, inspect logs

**Deliverables**:
- `tests/unit/` with pytest tests
- `tests/integration/` with full flows
- `tests-manual/` with driver scripts
- Test data fixtures in `tests/fixtures/`

**Estimated Time**: 3-4 days

---

## 5) Technical Specifications

### 5.1) Technology Stack

- **Language**: Python 3.13
- **Orchestration**: LangGraph + LangChain
- **LLM Provider**: 
  - **Default**: OpenAI GPT-4o (via LangChain)
  - **Configurable**: Anthropic Claude, Google Gemini
- **Database**: PostgreSQL 16 (via Docker Compose)
- **ORM**: SQLAlchemy 2.x
- **Migrations**: Alembic
- **Speech-to-Text**: 
  - **Primary**: OpenAI Whisper API
  - **Fallback**: faster-whisper (local, optional)
- **Document/Receipt Parsing**: 
  - **Primary**: LlamaParse (supports images + PDFs)
  - Output formats: Markdown + JSON (for tables)
- **Object Storage**: MinIO (local) or filesystem (MVP)
- **Logging**: structlog
- **Testing**: pytest
- **Prompt Management**:
  - **Phase 1**: Local files in `app/prompts/`
  - **Future**: Langfuse (centralized prompt management)

### 5.2) Project Structure

```
finanzas_personales_inteligentes/
├── app/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   └── ie_agent/
│   │       ├── __init__.py
│   │       ├── agent.py          # Main entry point
│   │       ├── graph.py          # LangGraph definition
│   │       ├── state.py          # State schema
│   │       └── nodes/
│   │           ├── __init__.py
│   │           ├── router.py
│   │           ├── extractors.py
│   │           ├── validator.py
│   │           └── storage.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── expense.py
│   │   ├── receipt.py
│   │   ├── user.py
│   │   ├── account.py
│   │   ├── trip.py
│   │   ├── category.py
│   │   └── card.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── extraction.py         # ExtractedExpense, ExtractedReceipt
│   │   ├── expense.py            # Pydantic schemas for API
│   │   └── receipt.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── expense_writer.py
│   │   └── receipt_writer.py
│   ├── tools/
│   │   ├── __init__.py
│   │   └── extraction/
│   │       ├── __init__.py
│   │       ├── text_extractor.py
│   │       ├── audio_extractor.py
│   │       └── receipt_parser.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── expense_extraction.py # Text extraction prompts
│   │   ├── receipt_parsing.py    # Receipt parsing prompts
│   │   └── category_mapping.py   # Category classification prompts
│   ├── database.py               # SQLAlchemy engine, session
│   ├── config.py                 # Settings (Pydantic BaseSettings)
│   └── logging_config.py         # structlog setup
├── alembic/
│   ├── versions/
│   │   └── 001_initial_schema.py
│   ├── env.py
│   └── alembic.ini
├── tests/
│   ├── unit/
│   │   ├── test_text_extractor.py
│   │   ├── test_audio_extractor.py
│   │   ├── test_receipt_parser.py
│   │   ├── test_expense_writer.py
│   │   └── test_ie_agent.py
│   ├── integration/
│   │   └── test_ie_agent_flows.py
│   └── fixtures/
│       ├── sample_audio.ogg
│       ├── sample_receipt.jpg
│       └── sample_texts.json
├── tests-manual/
│   ├── test_ie_agent_text.py
│   ├── test_ie_agent_audio.py
│   └── test_ie_agent_receipt.py
├── docs/
│   └── plans/
│       └── phase-1-ie-agent-and-storage.md (this file)
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── .env.example
```

### 5.3) Configuration (Environment Variables)

Add to `.env.example`:

```bash
# Database
POSTGRES_USER=finanzas_user
POSTGRES_PASSWORD=finanzas_password
POSTGRES_DB=finanzas_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# LLM Providers (Primary)
OPENAI_API_KEY=sk-...                    # ✅ Required - Already configured
                                          # Used for: Whisper API, GPT-4o text extraction

# LLM Providers (Optional - Multi-provider support)
ANTHROPIC_API_KEY=sk-ant-...             # Optional - Claude support
GOOGLE_API_KEY=...                        # Optional - Gemini support
LLM_PROVIDER=openai                       # Default: openai | anthropic | google

# LlamaIndex/LlamaParse
LLAMAPARSE_API_KEY=llx-...                # ✅ Required - Already configured
                                          # Used for: Receipt/invoice parsing (images + PDFs)

# Audio Processing
WHISPER_PROVIDER=api                      # Options: "api" (OpenAI) | "local" (faster-whisper)
WHISPER_MODEL=whisper-1                   # For API; or "base/medium/large" for local

# Object Storage (MinIO for MVP)
MINIO_HOST=localhost
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=finanzas-receipts

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json                           # json | console

# LangSmith (optional, for tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=finanzas-mvp

# Prompt Management (Future)
LANGFUSE_PUBLIC_KEY=pk-lf-...            # Optional - For Langfuse prompt management
LANGFUSE_SECRET_KEY=sk-lf-...            # Optional
LANGFUSE_HOST=https://cloud.langfuse.com # Optional
```

### 5.4) Dependencies

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # Web Framework
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    
    # Database
    "sqlalchemy>=2.0.25",
    "alembic>=1.13.1",
    "psycopg2-binary>=2.9.9",
    
    # Validation & Settings
    "pydantic>=2.6.0",
    "pydantic-settings>=2.1.0",
    
    # LangChain Core & Orchestration
    "langchain>=0.3.0",
    "langchain-core>=0.3.0",
    "langchain-openai>=0.2.0",              # Primary LLM provider
    "langgraph>=0.2.0",                     # Agent orchestration
    
    # LLM Providers (Multi-provider support)
    "langchain-anthropic>=0.2.0",          # Optional: Claude
    "langchain-google-genai>=0.1.0",       # Optional: Gemini
    
    # LlamaIndex & LlamaParse (Receipt/Document parsing)
    "llama-index-core>=0.11.0",
    "llama-parse>=0.5.0",
    
    # OpenAI SDK (Whisper API)
    "openai>=1.50.0",
    
    # Object Storage
    "minio>=7.2.0",
    
    # Logging
    "structlog>=24.1.0",
    "python-json-logger>=2.0.0",
    
    # File Processing
    "python-multipart>=0.0.6",
    "pillow>=10.2.0",
    "python-magic>=0.4.27",
    "python-dateutil>=2.8.0",
    
    # Optional: Local Whisper (heavier, offline-capable)
    "faster-whisper>=1.0.0",               # Optional: local ASR fallback
    
    # Optional: Langfuse (Future prompt management)
    "langfuse>=2.0.0",                      # Future: prompt versioning
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.26.0",
    "black>=24.1.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]
```

---

## 6) Success Criteria

**Phase 1 is complete when**:

1. ✅ All database tables created and migrated via Alembic
2. ✅ Text, audio, and image extraction tools functional with >80% accuracy on test cases
3. ✅ IE Agent successfully processes all input types end-to-end
4. ✅ Expense records persist to PostgreSQL with correct normalization
5. ✅ Idempotency verified (duplicate messages/images rejected)
6. ✅ Confidence scoring implemented and logged
7. ✅ Unit + integration tests pass with >80% coverage
8. ✅ Manual smoke tests documented and successful
9. ✅ Structured logging in place (no print statements)
10. ✅ Documentation complete (architecture, usage, troubleshooting)

---

## 7) Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LlamaParse/OCR API latency** | High | Cache results; implement timeout/retry logic; consider fallback OCR |
| **LLM hallucination in extraction** | High | Confidence scoring; validation rules; user confirmation flow |
| **Whisper transcription errors** | Medium | Store original audio; allow manual correction; use higher-quality models |
| **Currency code ambiguity** | Medium | Prompt engineering; context from trip/location; explicit user prompts |
| **Database schema changes** | Medium | Use Alembic migrations; version control; rollback plan |
| **Duplicate detection edge cases** | Low | Robust hashing; test with similar inputs; log collisions |

---

## 8) Prompt Management Strategy

### 8.1) Phase 1 Approach — Local Prompts

**Current Implementation**:
- Store all prompts in `app/prompts/` directory
- Define prompts as Python functions or classes
- Version control via Git
- Easy to iterate and test locally

**Structure**:
```python
# app/prompts/expense_extraction.py
from langchain.prompts import ChatPromptTemplate

EXPENSE_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are an expert at extracting expense information..."),
    ("user", "Extract expense data from: {text}")
])

# app/prompts/receipt_parsing.py
RECEIPT_PARSING_INSTRUCTIONS = """
Parse the following receipt data and extract:
- Merchant name
- Total amount and currency
- Line items with descriptions and amounts
- Date and time of transaction
...
"""
```

**Benefits**:
- Fast iteration during development
- No external dependencies
- Easy debugging and testing
- Full control over prompt versions

---

### 8.2) Future Migration — Langfuse Integration

**Target Implementation** (Phase 2+):
- Migrate prompts to Langfuse for centralized management
- Enable A/B testing of prompt variations
- Track prompt performance metrics
- Collaborative prompt engineering (non-technical users)
- Rollback capabilities

**Migration Path**:
1. Keep local prompts as fallback
2. Add Langfuse SDK integration
3. Fetch prompts from Langfuse API at runtime
4. Monitor performance differences
5. Gradually migrate all prompts

**Benefits**:
- Non-technical team members can edit prompts
- Version history and rollback
- A/B testing and analytics
- Prompt performance tracking
- Multi-environment support (dev/staging/prod)

**Configuration** (Future):
```python
# app/config.py
class Settings(BaseSettings):
    # Prompt source: "local" | "langfuse"
    prompt_source: str = "local"
    
    # Langfuse settings (optional)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
```

---

## 9) Next Steps (Phase 2 Preview)

After Phase 1:
- **FX Agent**: Add `fx_rate_daily` and `expense_fx_snapshot` tables
- **Card Agent**: Implement card defaults and nightly confirmations
- **API Layer**: Expose FastAPI endpoints for ingestion and queries
- **n8n Integration**: Connect WhatsApp gateway to API
- **RAG Setup**: Index receipts into Qdrant for semantic search
- **Langfuse Migration**: Move prompts to centralized management platform

---

## 10) Open Questions

1. **Category Mapping**: Use rule-based classifier or small ML model? (Proposed: LLM with few-shot examples)
2. **Confidence Threshold**: What's the minimum score to auto-confirm? (Proposed: 0.7 for MVP)
3. **Audio Storage**: Keep original audio files or just transcripts? (Proposed: Keep for 30 days)
4. **Image Storage**: MinIO local or cloud S3? (Proposed: MinIO for MVP, S3 later)
5. **Timezone Handling**: Store `occurred_at` in UTC or trip TZ? (Proposed: UTC with trip TZ metadata)
6. **Prompt Versioning**: When to migrate to Langfuse? (Proposed: After Phase 1 stabilization)

---

## 11) Timeline Summary

| Phase | Tasks | Duration | Cumulative |
|-------|-------|----------|------------|
| **1A** | Schema + Database | 2-3 days | 3 days |
| **1B** | Extraction Tools | 4-5 days | 8 days |
| **1C** | Storage Layer | 2-3 days | 11 days |
| **1D** | LangGraph Agent | 4-5 days | 16 days |
| **1E** | Testing & Docs | 3-4 days | 20 days |

**Total Estimated Duration**: ~3 weeks (with buffer)

---

## Appendix A — Sample Inputs & Outputs

### Text Input Example

```
Input: "Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa"

Expected Output:
{
  "amount": 45.50,
  "currency": "USD",
  "description": "comida en Whole Foods",
  "merchant": "Whole Foods",
  "category_candidate": "FOOD",
  "method": "card",
  "card_hint": "Visa",
  "confidence": 0.92
}
```

### Audio Input Example

```
Input: <audio_bytes> ("Twenty soles for taxi, paid cash")

Transcription: "Twenty soles for taxi, paid cash"

Expected Output:
{
  "amount": 20.00,
  "currency": "PEN",
  "description": "taxi",
  "category_candidate": "TRANSPORT",
  "method": "cash",
  "confidence": 0.85
}
```

### Receipt Image Example

```
Input: <receipt_image_bytes>

OCR Output:
{
  "merchant": "SuperMercado El Ahorro",
  "total_amount": 67.30,
  "currency": "PEN",
  "occurred_at": "2024-11-10T14:32:00",
  "line_items": [
    {"description": "Leche Gloria", "amount": 12.50},
    {"description": "Pan Integral", "amount": 8.00},
    ...
  ],
  "confidence": 0.88
}
```

---

## Appendix B — Logging Standards (Reference)

From `.cursor/rules/python-logging-standards.mdc`:

```python
import structlog

logger = structlog.get_logger(__name__)

# Example usage in IE Agent
logger.info(
    "expense_extracted",
    request_id=state["request_id"],
    user_id=state["user_id"],
    input_type=state["input_type"],
    confidence=state["confidence"],
    category=state["extracted_data"].category_candidate,
    amount=state["extracted_data"].amount,
    currency=state["extracted_data"].currency,
)
```

---

## Appendix C — Key Technical Decisions Summary

### API Keys Configuration
✅ **Already configured in `.env`**:
- `OPENAI_API_KEY` - Used for Whisper API and GPT-4o text extraction
- `LLAMAPARSE_API_KEY` - Used for receipt/document parsing (images + PDFs)

### Tool Selection Rationale

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Text Extraction** | LangChain + OpenAI GPT-4o | Structured output, configurable providers, excellent prompt control |
| **Audio Processing** | OpenAI Whisper API (primary) | API-based to avoid heavy model downloads; faster-whisper as fallback |
| **Receipt/Document Parsing** | LlamaParse | Handles both images and PDFs; outputs structured Markdown + JSON for tables |
| **Agent Orchestration** | LangGraph | Native state management, conditional routing, observability |
| **Prompt Management** | Local files → Langfuse | Start simple (local), migrate to centralized management later |

### Multi-Provider LLM Support
The architecture supports multiple LLM providers:
- **OpenAI** (default) - Best for structured output, widely tested
- **Anthropic Claude** - Alternative for text extraction
- **Google Gemini** - Alternative option

Configured via `LLM_PROVIDER` environment variable.

### Prompt Management Evolution
- **Phase 1**: Prompts in `app/prompts/` (Git versioned)
- **Phase 2+**: Migrate to Langfuse for:
  - Centralized management
  - A/B testing
  - Non-technical team collaboration
  - Performance tracking

---

**End of Phase 1 Plan**

