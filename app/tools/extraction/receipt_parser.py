"""
Receipt parser using LlamaParse for document understanding and LLM for structured extraction.
Extracts merchant info, amounts, line items, and metadata from receipts and bank statements.
"""

import hashlib
import tempfile
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from llama_parse import LlamaParse
from PIL import Image

from app.config import settings
from app.logging_config import get_logger
from app.schemas.extraction import ExtractedReceipt, LineItem

logger = get_logger(__name__)


def get_llamaparse_parser() -> LlamaParse:
    """
    Get configured LlamaParse instance.
    """
    if not settings.llamaparse_api_key:
        raise ValueError("LLAMAPARSE_API_KEY not configured")
        
    return LlamaParse(
        api_key=settings.llamaparse_api_key,
        result_type="markdown",
        verbose=True,
        language="en",  # Can be adjusted or made configurable
        num_workers=4,
    )


def parse_file_to_markdown(file_path: str | Path, **kwargs: Any) -> str:
    """
    Parse a file (PDF or Image) to Markdown using LlamaParse.
    
    Args:
        file_path: Path to the file
        **kwargs: Additional context
        
    Returns:
        str: The parsed markdown content
    """
    logger.info("parsing_file_with_llamaparse", path=str(file_path), **kwargs)
    
    try:
        parser = get_llamaparse_parser()
        documents = parser.load_data(str(file_path))
        
        if not documents:
            raise ValueError("LlamaParse returned no content")
            
        # Combine all pages into one markdown string
        full_markdown = "\n\n".join([doc.text for doc in documents])
        
        logger.info(
            "llamaparse_success", 
            content_length=len(full_markdown),
            pages=len(documents),
            **kwargs
        )
        return full_markdown
        
    except Exception as e:
        logger.error(
            "llamaparse_failed",
            error=str(e),
            error_type=type(e).__name__,
            **kwargs,
            exc_info=True
        )
        raise


def extract_receipt_from_markdown(
    markdown_text: str, 
    **kwargs: Any
) -> ExtractedReceipt:
    """
    Extract structured receipt data from Markdown using an LLM.
    
    Args:
        markdown_text: The markdown content from LlamaParse
        **kwargs: Additional context
        
    Returns:
        ExtractedReceipt: Structured data
    """
    logger.info("extracting_structure_from_markdown", **kwargs)
    
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=settings.openai_api_key
        )
        
        # Define the structured output parser
        structured_llm = llm.with_structured_output(ExtractedReceipt)
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are an expert receipt parser. 
            Extract structured data from the provided receipt/invoice markdown text.
            
            Guidelines:
            - Extract the merchant name, total amount, currency, and date.
            - Extract all line items with their prices and quantities.
            - Infer the category based on the merchant and items (e.g., 'in_house_food' for groceries, 'out_house_food' for restaurants).
            - If the currency is not explicitly stated but can be inferred from context (e.g., location), do so. Default to the most likely currency.
            - Confidence should be high (0.9+) if the text is clear, lower if ambiguous.
            """),
            ("user", "Receipt Content:\n\n{markdown_text}")
        ])
        
        chain = prompt_template | structured_llm
        
        result = chain.invoke({"markdown_text": markdown_text})
        
        # Attach the raw markdown to the result for reference
        result.raw_markdown = markdown_text
        
        logger.info(
            "llm_extraction_success",
            merchant=result.merchant,
            amount=float(result.total_amount),
            currency=result.currency,
            confidence=result.confidence,
            **kwargs
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "llm_extraction_failed",
            error=str(e),
            **kwargs,
            exc_info=True
        )
        raise


def extract_receipt_from_file(
    file_path: str | Path | bytes,
    **kwargs: Any,
) -> ExtractedReceipt:
    """
    Extract structured receipt data from image or PDF file.
    
    Orchestrates:
    1. File handling (bytes -> temp file if needed)
    2. LlamaParse (File -> Markdown)
    3. LLM (Markdown -> ExtractedReceipt)
    
    Args:
        file_path: Path to receipt image/PDF or bytes
        **kwargs: Additional context
        
    Returns:
        ExtractedReceipt with validated data
    """
    logger.info("extracting_receipt_from_file", **kwargs)
    
    # Handle bytes input by creating a temp file
    temp_file_path = None
    
    try:
        # Calculate hash and prepare file path
        if isinstance(file_path, bytes):
            content_hash = hashlib.sha256(file_path).hexdigest()
            
            # Create temp file
            # We try to guess extension or default to .tmp (LlamaParse might need extension)
            # For now, let's assume it could be an image or pdf. 
            # If we don't know, .pdf or .jpg is a safe bet for LlamaParse to try? 
            # Actually LlamaParse relies on extension.
            # Let's try to detect or default to .pdf if unknown, as it handles both.
            # But for bytes, we might want to pass a hint. 
            # For this implementation, we'll default to a generic name and hope LlamaParse detects magic numbers 
            # or we might need to add a 'filename' kwarg in the future.
            suffix = kwargs.get("filename", "").split(".")[-1] if kwargs.get("filename") else "tmp"
            if not suffix.startswith("."):
                suffix = f".{suffix}"
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_path)
                temp_file_path = Path(tmp.name)
                
            process_path = temp_file_path
            logger.debug("created_temp_file", path=str(temp_file_path))
            
        else:
            process_path = Path(file_path)
            if not process_path.exists():
                raise ValueError(f"File not found: {process_path}")
                
            with open(process_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()
                
        logger.debug("file_hash_calculated", hash=content_hash[:16])
        
        # Step 1: Parse to Markdown
        markdown_text = parse_file_to_markdown(process_path, **kwargs)
        
        # Step 2: Extract Structure
        receipt = extract_receipt_from_markdown(markdown_text, **kwargs)
        
        # Add raw text (markdown) to the result if not already set
        if not receipt.raw_markdown:
            receipt.raw_markdown = markdown_text
            
        return receipt
        
    finally:
        # Cleanup temp file if created
        if temp_file_path and temp_file_path.exists():
            try:
                os.unlink(temp_file_path)
                logger.debug("removed_temp_file", path=str(temp_file_path))
            except Exception as e:
                logger.warning("failed_to_remove_temp_file", path=str(temp_file_path), error=str(e))


# Alias for convenience
extract = extract_receipt_from_file


