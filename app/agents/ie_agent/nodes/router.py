"""
Router node for IE Agent.

Determines the input type and routes to the appropriate extraction node.
"""

import hashlib
from typing import Literal

from app.agents.ie_agent.state import IEAgentState, InputType
from app.logging_config import get_logger

logger = get_logger(__name__)


# MIME types for routing
IMAGE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/tiff"}
AUDIO_MIME_TYPES = {"audio/ogg", "audio/mpeg", "audio/mp3", "audio/wav", "audio/webm", "audio/m4a", "audio/aac"}
DOCUMENT_MIME_TYPES = {"application/pdf"}


def detect_input_type(state: IEAgentState) -> InputType:
    """
    Detect the input type from state.
    
    Detection logic:
    1. If input_type is already set and not 'unknown', use it
    2. If raw_input is string, it's text
    3. If raw_input is bytes, check file_type/filename
    4. Default to 'unknown'
    
    Args:
        state: Current agent state
        
    Returns:
        Detected InputType
    """
    # Already specified
    if state.get("input_type") and state["input_type"] != "unknown":
        return state["input_type"]
    
    raw_input = state.get("raw_input")
    
    # String input = text
    if isinstance(raw_input, str):
        return "text"
    
    # Bytes input = check MIME type
    if isinstance(raw_input, bytes):
        file_type = (state.get("file_type") or "").lower()
        filename = (state.get("filename") or "").lower()
        
        # Check by MIME type
        if file_type:
            if file_type in IMAGE_MIME_TYPES:
                return "image"
            if file_type in AUDIO_MIME_TYPES:
                return "audio"
            if file_type in DOCUMENT_MIME_TYPES:
                return "receipt"
        
        # Check by filename extension
        if filename:
            ext = filename.split(".")[-1] if "." in filename else ""
            if ext in {"jpg", "jpeg", "png", "gif", "webp"}:
                return "image"
            if ext in {"ogg", "mp3", "wav", "webm", "m4a", "mpeg"}:
                return "audio"
            if ext == "pdf":
                return "receipt"
    
    return "unknown"


def compute_content_hash(raw_input: str | bytes | None) -> str | None:
    """
    Compute SHA256 hash of input content.
    
    Args:
        raw_input: Text or bytes content
        
    Returns:
        Hex digest or None if no input
    """
    if raw_input is None:
        return None
    
    if isinstance(raw_input, str):
        data = raw_input.encode("utf-8")
    else:
        data = raw_input
    
    return hashlib.sha256(data).hexdigest()


def router_node(state: IEAgentState) -> IEAgentState:
    """
    Router node: Detects input type and prepares state for extraction.
    
    This is the first node in the graph. It:
    1. Detects the input type (text, audio, image, receipt)
    2. Computes content hash for idempotency
    3. Updates state with routing information
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with input_type and content_hash
    """
    request_id = state.get("request_id", "unknown")
    
    logger.info(
        "router_node_start",
        request_id=request_id,
        current_input_type=state.get("input_type"),
        has_raw_input=state.get("raw_input") is not None,
    )
    
    # Detect input type
    detected_type = detect_input_type(state)
    
    # Compute content hash
    content_hash = compute_content_hash(state.get("raw_input"))
    
    logger.info(
        "router_node_complete",
        request_id=request_id,
        detected_type=detected_type,
        content_hash=content_hash[:16] if content_hash else None,
    )
    
    # Return updated state
    return {
        **state,
        "input_type": detected_type,
        "content_hash": content_hash,
        "status": "routing",
    }


def get_extraction_route(state: IEAgentState) -> Literal["extract_text", "extract_audio", "extract_image", "error"]:
    """
    Conditional edge function: Determine which extraction node to route to.
    
    Used as a conditional edge in the graph to route based on input_type.
    
    Args:
        state: Current agent state
        
    Returns:
        Name of the next node to execute
    """
    input_type = state.get("input_type", "unknown")
    
    routing_map = {
        "text": "extract_text",
        "audio": "extract_audio",
        "image": "extract_image",
        "receipt": "extract_image",  # Receipts use same extraction as images
    }
    
    route = routing_map.get(input_type, "error")
    
    logger.debug(
        "routing_decision",
        request_id=state.get("request_id"),
        input_type=input_type,
        route=route,
    )
    
    return route

