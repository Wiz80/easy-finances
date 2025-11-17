# 💰 Finanzas Personales Inteligentes

> **WhatsApp-first Personal Finance Assistant focused on Travel Mode**

A multi-modal AI-powered expense tracking system that captures expenses via text, voice, and images. Built with LangGraph, LangChain, and PostgreSQL.

---

## 🎯 Project Vision

An intelligent personal finance assistant that helps travelers track expenses in real-time across multiple countries and currencies. The system uses AI to extract expense information from natural language, freeze daily FX rates, and provide conversational insights.

**Current Phase**: Phase 1 - IE Agent & Expense Storage (MVP)

---

## ✨ Features

### ✅ Implemented (Phase 1A & 1B - Partial)
- **Multi-modal Input Support**: Text, voice, and receipt images
- **Database Schema**: Complete PostgreSQL schema with Alembic migrations
- **8 MVP Categories**: Delivery, In-House Food, Out-House Food, Lodging, Transport, Tourism, Healthcare, Misc
- **Text Expense Extractor**: LangChain + OpenAI GPT-4o with structured output ✅
- **Audio Transcriber**: OpenAI Whisper API + Text Extractor pipeline ✅
- **Multi-Provider LLM Support**: OpenAI (default), Anthropic Claude, Google Gemini
- **Structured Logging**: `structlog` with JSON output
- **Configuration Management**: Pydantic Settings with `.env` support

### 🚧 In Progress (Phase 1B)
- Receipt Parser (LlamaParse integration)
- Storage Layer (Expense & Receipt Writers)

### 📋 Planned (Phase 1C-E)
- LangGraph IE Agent Orchestration
- Unit & Integration Tests
- Manual Smoke Tests

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     IE Agent (LangGraph)                 │
│                                                          │
│  ┌─────────────┐      ┌──────────────────────────┐    │
│  │   Router    │─────▶│  Extraction Tools Layer  │    │
│  │  (Intent)   │      │                          │    │
│  └─────────────┘      │  • Text Extractor ✅     │    │
│                       │  • Audio Transcriber ✅  │    │
│                       │  • Receipt Parser 🚧     │    │
│                       └──────────────────────────┘    │
│                                                          │
│                       ┌──────────────────────────┐    │
│                       │   Normalizer & Validator │    │
│                       └──────────────────────────┘    │
│                                                          │
│                       ┌──────────────────────────┐    │
│                       │    Storage Layer 🚧      │    │
│                       │  • Expense Writer        │    │
│                       │  • Receipt Metadata      │    │
│                       └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                              ▼
                     ┌──────────────────┐
                     │   PostgreSQL     │
                     │   • expenses     │
                     │   • receipts     │
                     │   • users        │
                     │   • categories   │
                     └──────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Docker & Docker Compose
- uv (Python package manager) or pip
- PostgreSQL 16 (via Docker)

### 1. Clone and Install

```bash
# Clone repository
git clone <repo-url>
cd finanzas_personales_inteligentes

# Install dependencies with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### 2. Configure Environment

```bash
# Copy environment template
cp env.example .env

# Edit .env with your API keys
nano .env
```

**Required API Keys**:
- `OPENAI_API_KEY`: For GPT-4o and Whisper API
- `LLAMAPARSE_API_KEY`: For receipt parsing

### 3. Start Services

```bash
# Start PostgreSQL, Qdrant, and n8n
docker-compose up -d

# Check services
docker-compose ps
```

### 4. Run Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Verify database
alembic current
```

### 5. Test Text Extractor

```bash
# Run manual tests
python tests-manual/test_text_extractor.py
```

---

## 📚 Documentation

- [Phase 1 Plan](docs/plans/phase-1-ie-agent-and-storage.md) - Complete development plan
- [Text Extractor Usage](docs/tools/text-extractor-usage.md) - Text extraction tool
- [Audio Extractor Usage](docs/tools/audio-extractor-usage.md) - Audio transcription tool
- [Context Document](docs/context.md) - Project context and goals

### Rules & Standards
- [Project Context](cursor/rules/project-context-travel-assistant.mdc)
- [Python Logging Standards](.cursor/rules/python-logging-standards.mdc)
- [FX Snapshot & Idempotency](.cursor/rules/fx-snapshot-and-idempotency.mdc)
- [Security & Privacy](.cursor/rules/security-and-privacy.mdc)

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language** | Python 3.13 | Core application |
| **AI Orchestration** | LangGraph + LangChain | Agent coordination |
| **LLM Providers** | OpenAI, Anthropic, Google | Text extraction |
| **Database** | PostgreSQL 16 | Relational data |
| **ORM** | SQLAlchemy 2.x | Database models |
| **Migrations** | Alembic | Schema versioning |
| **Vector DB** | Qdrant | Semantic search (Phase 2) |
| **OCR** | LlamaParse | Receipt parsing |
| **Speech-to-Text** | OpenAI Whisper API | Audio transcription |
| **Logging** | structlog | Structured logs |
| **Testing** | pytest | Unit/integration tests |

---

## 📦 Project Structure

```
finanzas_personales_inteligentes/
├── app/
│   ├── agents/              # LangGraph agents
│   │   └── ie_agent/        # Information Extraction agent (Phase 1D)
│   ├── models/              # SQLAlchemy models ✅
│   │   ├── user.py
│   │   ├── account.py
│   │   ├── card.py
│   │   ├── category.py
│   │   ├── trip.py
│   │   ├── expense.py
│   │   └── receipt.py
│   ├── schemas/             # Pydantic schemas ✅
│   │   └── extraction.py    # ExtractedExpense, ExtractedReceipt
│   ├── tools/               # Extraction tools
│   │   └── extraction/
│   │       ├── text_extractor.py ✅
│   │       ├── audio_extractor.py ✅
│   │       └── receipt_parser.py 🚧
│   ├── prompts/             # LLM prompts ✅
│   │   └── expense_extraction.py
│   ├── storage/             # Data persistence (Phase 1C)
│   ├── config.py            # Settings ✅
│   ├── database.py          # DB session management ✅
│   └── logging_config.py    # Logging setup ✅
├── alembic/                 # Database migrations ✅
│   └── versions/
│       ├── b0035a0e9246_initial_schema.py
│       └── 4cffcdb68f5e_seed_categories_mvp.py
├── tests/
│   ├── unit/                # Unit tests (Phase 1E)
│   ├── integration/         # Integration tests (Phase 1E)
│   └── fixtures/            # Test data
├── tests-manual/            # Manual test scripts ✅
│   └── test_text_extractor.py
├── docs/
│   ├── plans/               # Development plans
│   └── tools/               # Tool documentation
├── docker-compose.yml       # Services configuration
├── pyproject.toml          # Dependencies ✅
└── README.md               # This file
```

---

## 🔑 Configuration

### Environment Variables

Key variables in `.env`:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=finanzas_db
POSTGRES_USER=finanzas_user
POSTGRES_PASSWORD=your_password

# LLM Provider (Primary)
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai  # options: openai, anthropic, google

# LlamaParse (Receipt Parsing)
LLAMAPARSE_API_KEY=llx-...

# Audio Processing
WHISPER_PROVIDER=api  # options: api, local
WHISPER_MODEL=whisper-1

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json  # options: json, console
```

---

## 💻 Usage Examples

### Text Expense Extraction

```python
from app.tools.extraction.text_extractor import extract_expense_from_text

# Extract from Spanish text
text = "Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa"
expense = extract_expense_from_text(text)

print(f"{expense.amount} {expense.currency}")  # 45.50 USD
print(f"Category: {expense.category_candidate}")  # out_house_food
print(f"Confidence: {expense.confidence}")  # 0.92
```

### Audio Expense Extraction

```python
from app.tools.extraction.audio_extractor import extract_expense_from_audio

# Extract from audio file (Whisper API transcription + text extraction)
expense = extract_expense_from_audio("voice_note.ogg")

print(f"{expense.amount} {expense.currency}")  # 20.00 PEN
print(f"Category: {expense.category_candidate}")  # transport
print(f"Transcription: {expense.notes}")  # Original audio text
```

### Database Queries

```python
from app.database import SessionLocal
from app.models import Category, Expense

# Get all categories
with SessionLocal() as db:
    categories = db.query(Category).filter(Category.is_active == True).all()
    for cat in categories:
        print(f"{cat.name} ({cat.slug})")
```

---

## 🧪 Testing

### Run Manual Tests

```bash
# Test text extractor
python tests-manual/test_text_extractor.py

# Test audio extractor
python tests-manual/test_audio_extractor.py

# Generate synthetic audio test files first
python tests-manual/generate_test_audio.py

# Test with your own audio file
python tests-manual/test_audio_extractor.py path/to/your/audio.ogg

# Output shows:
# - Extracted data for each test case
# - Success/failure rate
# - Confidence score distribution
```

### Run Unit Tests (when implemented)

```bash
pytest tests/unit/ -v

# With coverage
pytest --cov=app tests/
```

---

## 📊 Database Schema

### Core Tables

- **user**: User profiles and preferences
- **account**: Bank accounts, wallets
- **card**: Credit/debit cards
- **category**: Expense categories (8 MVP categories)
- **trip**: Travel periods for budgeting
- **expense**: Core expense records
- **receipt**: Receipt metadata and OCR output

### Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# View history
alembic history
```

---

## 🔐 Security & Privacy

- ✅ No PII in logs (structured logging with redaction)
- ✅ API keys in environment variables only
- ✅ Pydantic validation for all inputs
- ✅ Prepared for row-level security (multi-tenant)
- 🚧 Receipt signed URLs with TTL (Phase 2)

---

## 📈 Development Roadmap

### Phase 1A: Foundation ✅ (COMPLETED)
- [x] Database schema design
- [x] Alembic migrations setup
- [x] SQLAlchemy models
- [x] MVP categories seeded
- [x] Configuration management
- [x] Logging infrastructure

### Phase 1B: Extraction Tools 🚧 (IN PROGRESS)
- [x] Text Extractor with LangChain + OpenAI
- [ ] Audio Transcriber (Whisper API)
- [ ] Receipt Parser (LlamaParse)
- [ ] Unit tests for extractors

### Phase 1C: Storage Layer (NEXT)
- [ ] Expense Writer with idempotency
- [ ] Receipt Writer with content hashing
- [ ] Integration tests

### Phase 1D: LangGraph Agent
- [ ] Agent state definition
- [ ] Router, Extractor, Validator, Storage nodes
- [ ] End-to-end agent orchestration

### Phase 1E: Testing & Validation
- [ ] Complete unit test suite
- [ ] Integration test flows
- [ ] Manual smoke tests

### Phase 2+: Advanced Features
- [ ] FX Agent (rate freezing)
- [ ] Card Agent (nightly confirmations)
- [ ] FastAPI endpoints
- [ ] n8n WhatsApp integration
- [ ] RAG with Qdrant

---

## 🐛 Troubleshooting

### Services won't start

```bash
docker-compose logs
docker-compose down -v
docker-compose up -d
```

### Migration issues

```bash
# Check current revision
alembic current

# Reset database (CAUTION: deletes data)
alembic downgrade base
alembic upgrade head
```

### Text extractor errors

```bash
# Check API key
echo $OPENAI_API_KEY

# Test with minimal input
python -c "from app.tools.extraction.text_extractor import extract; print(extract('20 dollars cash'))"
```

---

## 🤝 Contributing

1. Follow [Python Logging Standards](.cursor/rules/python-logging-standards.mdc)
2. Use structured Pydantic schemas (see [schemas README](.cursor/rules/docs-structure-and-references.mdc))
3. Write tests for new extractors
4. Update documentation

---

## 📝 License

[Your License Here]

---

## 📧 Support

For issues and questions, please open an issue on GitHub or refer to the [Phase 1 Plan](docs/plans/phase-1-ie-agent-and-storage.md).

---

**Built with ❤️ using LangChain, LangGraph, and FastAPI**
