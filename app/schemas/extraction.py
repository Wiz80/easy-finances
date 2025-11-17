"""
Pydantic schemas for expense extraction from multi-modal inputs.
Used by extraction tools to return structured, validated data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ExtractedExpense(BaseModel):
    """
    Structured expense data extracted from text or audio input.
    Represents a single expense with normalized fields.
    """

    amount: Decimal = Field(
        ...,
        description="Expense amount as a decimal number",
        gt=0,
        examples=[20.50, 100.00, 15.99],
    )
    currency: str = Field(
        ...,
        description="ISO 4217 currency code (3 letters uppercase)",
        min_length=3,
        max_length=3,
        examples=["USD", "PEN", "COP", "MXN", "EUR"],
    )
    description: str = Field(
        ...,
        description="Brief description of the expense",
        min_length=1,
        max_length=500,
        examples=["groceries", "taxi to airport", "dinner at restaurant"],
    )
    category_candidate: str = Field(
        ...,
        description="Suggested category slug for the expense",
        examples=[
            "delivery",
            "in_house_food",
            "out_house_food",
            "lodging",
            "transport",
            "tourism",
            "healthcare",
            "misc",
        ],
    )
    method: Literal["cash", "card", "transfer"] = Field(
        ...,
        description="Payment method used",
        examples=["cash", "card"],
    )
    merchant: str | None = Field(
        None,
        description="Merchant or vendor name if mentioned",
        max_length=255,
        examples=["Whole Foods", "Uber", "Hotel Marriott"],
    )
    card_hint: str | None = Field(
        None,
        description="Card type or last digits if mentioned (Visa, Mastercard, etc)",
        max_length=50,
        examples=["Visa", "Mastercard", "4532"],
    )
    occurred_at: datetime | None = Field(
        None,
        description="Date/time when expense occurred if mentioned, otherwise None",
    )
    notes: str | None = Field(
        None,
        description="Additional notes or context",
        max_length=1000,
    )
    confidence: float = Field(
        ...,
        description="Confidence score for the extraction (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    raw_input: str = Field(
        ..., description="Original input text that was processed", max_length=2000
    )

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        """Ensure currency code is uppercase."""
        return v.upper()

    @field_validator("category_candidate")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate category is one of the known MVP categories."""
        valid_categories = {
            "delivery",
            "in_house_food",
            "out_house_food",
            "lodging",
            "transport",
            "tourism",
            "healthcare",
            "misc",
        }
        v_lower = v.lower()
        if v_lower not in valid_categories:
            # Default to misc if category is unknown
            return "misc"
        return v_lower

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 45.50,
                "currency": "USD",
                "description": "comida en Whole Foods",
                "merchant": "Whole Foods",
                "category_candidate": "out_house_food",
                "method": "card",
                "card_hint": "Visa",
                "occurred_at": None,
                "notes": None,
                "confidence": 0.92,
                "raw_input": "Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa",
            }
        }


class LineItem(BaseModel):
    """Individual line item from a receipt."""

    description: str = Field(..., description="Item description", max_length=255)
    quantity: int | None = Field(None, description="Quantity of items", ge=1)
    unit_price: Decimal | None = Field(
        None, description="Price per unit", gt=0, decimal_places=2
    )
    amount: Decimal = Field(..., description="Total amount for this line item", gt=0)


class ExtractedReceipt(BaseModel):
    """
    Structured receipt data extracted from images or PDFs.
    Includes merchant info, line items, and metadata.
    """

    merchant: str = Field(
        ...,
        description="Merchant or business name",
        min_length=1,
        max_length=255,
        examples=["SuperMercado El Ahorro", "Starbucks", "Shell Gas Station"],
    )
    total_amount: Decimal = Field(
        ..., description="Total amount on receipt", gt=0, decimal_places=2
    )
    currency: str = Field(
        ...,
        description="ISO 4217 currency code",
        min_length=3,
        max_length=3,
        examples=["USD", "PEN", "COP"],
    )
    occurred_at: datetime | None = Field(
        None, description="Date and time from receipt if available"
    )
    line_items: list[LineItem] = Field(
        default_factory=list, description="Individual items from receipt"
    )
    tax_amount: Decimal | None = Field(
        None, description="Tax amount if separately listed", ge=0
    )
    tip_amount: Decimal | None = Field(
        None, description="Tip amount if separately listed", ge=0
    )
    payment_method: str | None = Field(
        None,
        description="Payment method mentioned on receipt",
        max_length=50,
        examples=["Cash", "Visa ***4532", "Mastercard"],
    )
    receipt_number: str | None = Field(
        None, description="Receipt or transaction number", max_length=100
    )
    category_candidate: str = Field(
        default="misc",
        description="Suggested category based on merchant/items",
        examples=[
            "delivery",
            "in_house_food",
            "out_house_food",
            "lodging",
            "transport",
            "tourism",
            "healthcare",
            "misc",
        ],
    )
    confidence: float = Field(
        ..., description="OCR confidence score (0.0 to 1.0)", ge=0.0, le=1.0
    )
    raw_text: str | None = Field(
        None, description="Raw OCR text output", max_length=10000
    )
    raw_markdown: str | None = Field(
        None, description="LlamaParse markdown output", max_length=10000
    )

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        """Ensure currency code is uppercase."""
        return v.upper()

    @field_validator("category_candidate")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate category is one of the known MVP categories."""
        valid_categories = {
            "delivery",
            "in_house_food",
            "out_house_food",
            "lodging",
            "transport",
            "tourism",
            "healthcare",
            "misc",
        }
        v_lower = v.lower()
        if v_lower not in valid_categories:
            return "misc"
        return v_lower

    class Config:
        json_schema_extra = {
            "example": {
                "merchant": "SuperMercado El Ahorro",
                "total_amount": 67.30,
                "currency": "PEN",
                "occurred_at": "2024-11-10T14:32:00",
                "line_items": [
                    {"description": "Leche Gloria", "amount": 12.50},
                    {"description": "Pan Integral", "amount": 8.00},
                ],
                "tax_amount": 5.50,
                "category_candidate": "in_house_food",
                "confidence": 0.88,
                "raw_text": "...",
                "raw_markdown": "...",
            }
        }

