"""
Embeddings Service.

Handles OpenAI embeddings and Qdrant vector search.
"""

from typing import Any

from openai import OpenAI
from qdrant_client import QdrantClient

from src.config import settings

# Lazy-loaded clients
_openai_client: OpenAI | None = None
_qdrant_client: QdrantClient | None = None


def get_openai_client() -> OpenAI:
    """Get OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
        )
    return _qdrant_client


def generate_embedding(text: str) -> list[float]:
    """
    Generate embedding for text using OpenAI.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector (1536 dimensions)
    """
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def search_similar(
    collection: str,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Search for similar items in Qdrant.
    
    Args:
        collection: Collection name
        query: Query text
        limit: Max results
        
    Returns:
        List of similar items with scores
    """
    qdrant = get_qdrant_client()
    
    try:
        embedding = generate_embedding(query)
        results = qdrant.search(
            collection_name=collection,
            query_vector=embedding,
            limit=limit,
        )
        
        return [
            {
                "content": r.payload.get("content") or r.payload.get("sql"),
                "question": r.payload.get("question"),
                "table_name": r.payload.get("table_name"),
                "score": r.score,
                **r.payload,
            }
            for r in results
        ]
    except Exception as e:
        # Collections might not exist yet
        return []

