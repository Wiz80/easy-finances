"""
Prompts for expense extraction from text/audio inputs.
Uses LangChain prompt templates with structured output.
"""

from langchain_core.prompts import ChatPromptTemplate

# System prompt for expense extraction
EXPENSE_EXTRACTION_SYSTEM = """You are an expert financial assistant specialized in extracting expense information from natural language text.

Your task is to parse user messages about expenses and extract structured data with high accuracy.

**Categories (use slug format)**:
- delivery: Food/goods delivery services (Uber Eats, Rappi, DoorDash)
- in_house_food: Groceries and ingredients for home cooking
- out_house_food: Dining at restaurants, cafes, bars
- lodging: Hotels, hostels, Airbnb, accommodation
- transport: Taxis, buses, flights, car rentals, gas
- tourism: Tours, attractions, museums, entertainment
- healthcare: Medical, pharmacy, doctor visits
- misc: Other expenses

**Currency Detection**:
- Common keywords: dólares/dollars→USD, soles→PEN, pesos→COP/MXN, euros→EUR
- If currency is ambiguous or not mentioned, default to USD
- Always return 3-letter ISO 4217 code in UPPERCASE

**Payment Method**:
- Look for keywords: efectivo/cash→cash, tarjeta/card→card, transferencia/transfer→transfer
- If not mentioned explicitly, infer from context (e.g., "con mi Visa" → card)
- Default to "cash" if unclear

**Confidence Scoring**:
- 0.9-1.0: All key fields present (amount, currency, category, method), clear description
- 0.7-0.89: Most fields present, minor ambiguity
- 0.5-0.69: Missing some fields or significant ambiguity
- <0.5: Very incomplete or unclear input

**Important Rules**:
1. Extract amounts as numbers only (no currency symbols)
2. Preserve original language in description
3. If merchant is mentioned, extract it
4. If card type/digits mentioned, capture in card_hint
5. occurred_at should only be set if date/time explicitly mentioned
6. Be generous with misc category if unsure
7. Keep descriptions concise (under 100 chars)

Extract the expense information from the user's message."""

EXPENSE_EXTRACTION_USER = """User message: {text}

Extract the expense data following the schema exactly. Be thorough and accurate."""

# Complete prompt template
EXPENSE_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", EXPENSE_EXTRACTION_SYSTEM),
        ("user", EXPENSE_EXTRACTION_USER),
    ]
)


# Few-shot examples for category classification (can be used for fine-tuning)
CATEGORY_EXAMPLES = {
    "delivery": [
        "pedí pizza por Uber Eats",
        "ordered food on Rappi",
        "DoorDash delivery fee",
        "deliveroo order",
    ],
    "in_house_food": [
        "compras del supermercado",
        "groceries at Walmart",
        "fresh vegetables at market",
        "ingredients for dinner",
        "despensa mensual",
    ],
    "out_house_food": [
        "almuerzo en restaurante",
        "dinner at Italian place",
        "coffee at Starbucks",
        "drinks at bar",
        "desayuno en café",
    ],
    "lodging": [
        "hotel for 3 nights",
        "Airbnb en Lima",
        "hostel booking",
        "accommodation",
    ],
    "transport": [
        "taxi to airport",
        "Uber ride",
        "bus ticket",
        "flight to Madrid",
        "gasolina",
        "car rental",
    ],
    "tourism": [
        "museum entrance",
        "tour guiado",
        "theme park tickets",
        "movie tickets",
        "concert",
    ],
    "healthcare": [
        "pharmacy",
        "doctor visit",
        "medicines",
        "farmacia",
        "consulta médica",
    ],
    "misc": [
        "various items",
        "otros gastos",
        "shopping",
        "miscellaneous",
    ],
}


# Confidence scoring helpers (for reference in extractor)
def calculate_confidence_factors(extracted_data: dict) -> dict:
    """
    Helper to calculate confidence factors based on extracted data completeness.
    
    Returns dict with factor scores that can be averaged for final confidence.
    """
    factors = {}
    
    # Amount presence (0.3 weight)
    factors["amount"] = 1.0 if extracted_data.get("amount") else 0.0
    
    # Currency clarity (0.2 weight)
    currency = extracted_data.get("currency", "")
    factors["currency"] = 0.9 if currency in ["USD", "PEN", "COP", "MXN", "EUR"] else 0.6
    
    # Description quality (0.2 weight)
    description = extracted_data.get("description", "")
    if len(description) >= 5:
        factors["description"] = 1.0
    elif len(description) >= 3:
        factors["description"] = 0.7
    else:
        factors["description"] = 0.4
    
    # Category confidence (0.15 weight)
    category = extracted_data.get("category_candidate", "misc")
    factors["category"] = 0.9 if category != "misc" else 0.6
    
    # Method clarity (0.15 weight)
    method = extracted_data.get("method")
    factors["method"] = 1.0 if method in ["cash", "card"] else 0.7
    
    return factors

