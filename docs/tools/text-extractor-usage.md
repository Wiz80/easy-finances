## # Text Extractor - Usage Guide

## Overview

The Text Extractor is a LangChain-based tool that uses LLMs with structured output to extract expense information from natural language text. It supports multiple LLM providers (OpenAI, Anthropic, Google) and returns validated Pydantic models.

## Features

- **Multi-provider support**: OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini)
- **Structured output**: Enforced Pydantic schema validation
- **Confidence scoring**: Automatic confidence calculation based on field completeness
- **Multi-language**: Works with English, Spanish, and other languages
- **Category classification**: Automatic mapping to MVP categories
- **Logging**: Structured logs with contextual information

## Architecture

```
User Input (Text)
       ↓
  Text Extractor
       ↓
  LangChain Prompt
       ↓
  LLM (OpenAI/Anthropic/Google)
       ↓
  Structured Output (Pydantic)
       ↓
  Confidence Adjustment
       ↓
  ExtractedExpense
```

## Installation

Already included in project dependencies. Make sure you have:

```bash
# Install dependencies
uv pip install -e .

# Or if using pip
pip install -e .
```

## Configuration

Set your LLM provider in `.env`:

```bash
# Primary provider (required)
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai  # options: openai, anthropic, google

# Optional providers
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

## Usage

### Basic Usage

```python
from app.tools.extraction.text_extractor import extract_expense_from_text

# Extract expense from text
text = "Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa"
expense = extract_expense_from_text(text)

print(f"Amount: {expense.amount} {expense.currency}")
print(f"Category: {expense.category_candidate}")
print(f"Method: {expense.method}")
print(f"Confidence: {expense.confidence}")
```

### With Context (for logging)

```python
expense = extract_expense_from_text(
    text,
    user_id="user123",
    request_id="req456"
)
```

### Output Schema

The extractor returns an `ExtractedExpense` object with:

```python
class ExtractedExpense:
    amount: Decimal              # Required
    currency: str                # ISO 4217 (3 letters)
    description: str             # Brief description
    category_candidate: str      # MVP category slug
    method: str                  # cash, card, or transfer
    merchant: str | None         # Merchant name if mentioned
    card_hint: str | None        # Card type/digits if mentioned
    occurred_at: datetime | None # Date/time if mentioned
    notes: str | None            # Additional notes
    confidence: float            # 0.0 to 1.0
    raw_input: str               # Original text
```

## Supported Categories

The extractor classifies expenses into these MVP categories:

| Slug | Description | Keywords |
|------|-------------|----------|
| `delivery` | Food/goods delivery | uber eats, rappi, doordash, delivery |
| `in_house_food` | Groceries for home | supermarket, groceries, ingredients |
| `out_house_food` | Restaurants, cafes | restaurant, cafe, dining, bar |
| `lodging` | Hotels, Airbnb | hotel, hostel, airbnb, accommodation |
| `transport` | Taxis, flights, buses | taxi, uber, bus, flight, gas |
| `tourism` | Activities, attractions | tour, museum, entertainment |
| `healthcare` | Medical, pharmacy | doctor, pharmacy, medicine |
| `misc` | Other expenses | miscellaneous, other, various |

## Confidence Scoring

Confidence is calculated based on:

- **Amount clarity** (30%): Is the amount clearly stated?
- **Currency identification** (20%): Is currency explicitly mentioned or inferable?
- **Description quality** (20%): Is the description meaningful?
- **Category confidence** (15%): How certain is the category classification?
- **Payment method** (15%): Is the method clearly stated?

### Confidence Ranges

- **0.9-1.0**: Excellent - All fields present, no ambiguity
- **0.7-0.89**: Good - Most fields present, minor ambiguity
- **0.5-0.69**: Fair - Some missing fields or ambiguity
- **< 0.5**: Poor - Incomplete or very unclear

## Examples

### Example 1: Complete Information (High Confidence)

```python
text = "Dinner at La Trattoria, 85 USD with my Visa card"
expense = extract_expense_from_text(text)

# Result:
# amount: 85.00
# currency: USD
# description: Dinner at La Trattoria
# merchant: La Trattoria
# category: out_house_food
# method: card
# card_hint: Visa
# confidence: ~0.95
```

### Example 2: Minimal Information (Lower Confidence)

```python
text = "Gasté 50"
expense = extract_expense_from_text(text)

# Result:
# amount: 50.00
# currency: USD (default)
# description: Gasté 50
# category: misc
# method: cash (default)
# confidence: ~0.55
```

### Example 3: Spanish Input

```python
text = "Compré medicinas en la farmacia, 80 pesos mexicanos en efectivo"
expense = extract_expense_from_text(text)

# Result:
# amount: 80.00
# currency: MXN
# description: medicinas en la farmacia
# category: healthcare
# method: cash
# confidence: ~0.88
```

## Testing

### Manual Testing

```bash
# Run manual test script
python tests-manual/test_text_extractor.py
```

This will run multiple test cases and show:
- Extracted data for each case
- Success/failure rate
- Confidence score distribution

### Unit Testing

```bash
# Run unit tests (when implemented)
pytest tests/unit/test_text_extractor.py -v
```

## Error Handling

The extractor raises exceptions for:

- **ValueError**: Empty input text
- **ValueError**: Missing/invalid API keys
- **ValidationError**: LLM output doesn't match schema

Always wrap calls in try-except:

```python
from pydantic import ValidationError

try:
    expense = extract_expense_from_text(text)
except ValueError as e:
    logger.error("Invalid input", error=str(e))
except ValidationError as e:
    logger.error("Schema validation failed", error=str(e))
```

## Performance

- **Latency**: ~1-3 seconds per extraction (depends on provider)
- **Accuracy**: Expected >85% on clear inputs
- **Cost**: ~$0.001-0.005 per extraction (varies by provider)

## Logging

All extractions are logged with structured data:

```json
{
  "event": "expense_extracted_successfully",
  "amount": 45.50,
  "currency": "USD",
  "category": "out_house_food",
  "method": "card",
  "confidence": 0.92,
  "provider": "openai",
  "text_length": 65
}
```

## Next Steps

- Add unit tests with pytest
- Implement caching for repeated similar inputs
- Add batch processing support
- Fine-tune confidence scoring algorithm
- Support for date/time extraction improvements

## Troubleshooting

### Issue: Low Confidence Scores

**Solution**: Provide more context in input text. Include:
- Explicit currency
- Clear payment method
- Merchant name if known
- Category hints

### Issue: Wrong Category

**Solution**: Categories are inferred from keywords. For edge cases:
- Use more descriptive text
- Add merchant name (helps with classification)
- Consider adding category override parameter

### Issue: Currency Detection

**Solution**: 
- Always mention currency explicitly when possible
- Use common currency names (dollars, pesos, euros, soles)
- System defaults to USD if ambiguous

## Contributing

When improving the text extractor:

1. Update prompts in `app/prompts/expense_extraction.py`
2. Adjust confidence scoring in extractor
3. Add test cases to manual tests
4. Update documentation

## References

- [LangChain Structured Output](https://python.langchain.com/docs/modules/model_io/chat/structured_output)
- [Pydantic Models](https://docs.pydantic.dev/latest/)
- [Phase 1 Plan](../plans/phase-1-ie-agent-and-storage.md)


