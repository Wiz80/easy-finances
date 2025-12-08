"""
Vanna AI Service for Vanna 2.x.

Provides NL to SQL conversion using the new Agent-based architecture.

Key components:
- LlmService: For generating SQL from natural language
- QdrantAgentMemory: For storing and retrieving similar patterns (RAG)
"""

import logging
import uuid
from typing import Any

from app.config import settings
from app.prompts.sql_generation import SQL_GENERATION_SYSTEM, SQL_GENERATION_CONTEXT_TEMPLATE

logger = logging.getLogger(__name__)


def create_llm_service():
    """
    Create and configure an LLM service based on settings.
    
    Returns:
        Configured LlmService instance (OpenAI or Anthropic)
    """
    if settings.llm_provider == "anthropic":
        from vanna.integrations.anthropic import AnthropicLlmService
        
        return AnthropicLlmService(
            model="claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
        )
    else:
        # Default: OpenAI
        from vanna.integrations.openai import OpenAILlmService
        
        return OpenAILlmService(
            model="gpt-4o",
            api_key=settings.openai_api_key,
        )


def create_agent_memory():
    """
    Create a Qdrant-based agent memory for RAG.
    
    Returns:
        Configured QdrantAgentMemory instance
    """
    from vanna.integrations.qdrant import QdrantAgentMemory
    
    # Build Qdrant URL
    if settings.qdrant_api_key:
        # Cloud Qdrant
        url = f"https://{settings.qdrant_host}:{settings.qdrant_http_port}"
    else:
        # Local Qdrant
        url = f"http://{settings.qdrant_host}:{settings.qdrant_http_port}"
    
    return QdrantAgentMemory(
        collection_name=settings.vanna_sql_collection,
        url=url,
        api_key=settings.qdrant_api_key,
        dimension=settings.vanna_vector_dimension,
    )


def create_mock_context(agent_memory):
    """
    Create a mock ToolContext for memory operations.
    
    Vanna 2.x requires a ToolContext for memory operations.
    Since we're using it outside the Agent framework, we create a mock context.
    
    Args:
        agent_memory: The AgentMemory instance
        
    Returns:
        ToolContext instance
    """
    from vanna.core.tool.models import ToolContext
    from vanna.core.user.models import User
    
    mock_user = User(
        id="system",
        username="coach_agent",
        metadata={"type": "service_account"},
    )
    
    return ToolContext(
        user=mock_user,
        conversation_id="coach_agent_context",
        request_id=str(uuid.uuid4()),
        agent_memory=agent_memory,
        metadata={"source": "coach_agent"},
    )


class VannaService:
    """
    Service wrapper for Vanna 2.x AI operations.
    
    Uses the new Agent-based architecture with:
    - LlmService for LLM calls (OpenAI/Anthropic)
    - QdrantAgentMemory for RAG/training data
    
    This service is used by the coach_agent to:
    1. Generate SQL from natural language questions
    2. Store and retrieve training patterns
    """

    _instance = None
    _llm_service = None
    _agent_memory = None

    def __init__(self):
        """Initialize Vanna 2.x service components."""
        if VannaService._instance is None:
            try:
                VannaService._llm_service = create_llm_service()
                VannaService._agent_memory = create_agent_memory()
                VannaService._instance = self
                logger.info("Vanna 2.x service initialized successfully")
                logger.info(f"  LLM Provider: {settings.llm_provider}")
                logger.info(f"  Qdrant Collection: {settings.vanna_sql_collection}")
            except Exception as e:
                logger.error(f"Failed to initialize Vanna service: {e}")
                raise

    @property
    def llm_service(self):
        """Get the LLM service."""
        return VannaService._llm_service

    @property
    def agent_memory(self):
        """Get the agent memory."""
        return VannaService._agent_memory

    async def generate_sql(self, question: str) -> dict[str, Any]:
        """
        Generate SQL from a natural language question.
        
        Process:
        1. Search for similar questions in agent memory (RAG)
        2. Build context from similar patterns
        3. Send to LLM to generate SQL
        4. Clean and return the SQL
        
        Args:
            question: Natural language question
            
        Returns:
            {
                "success": bool,
                "sql": str | None,
                "error": str | None,
                "similar_patterns": list[dict] | None
            }
        """
        try:
            from vanna.core.llm.models import LlmRequest, LlmMessage
            from vanna.core.user.models import User
            
            # Create context for memory operations
            context = create_mock_context(self.agent_memory)
            
            # Search for similar patterns in agent memory
            similar_patterns = []
            try:
                similar_results = await self.agent_memory.search_similar_usage(
                    question=question,
                    context=context,
                    limit=5,
                    similarity_threshold=0.5,
                )
                similar_patterns = similar_results
            except Exception as e:
                logger.warning(f"Error searching similar patterns: {e}")
            
            # Build context from similar patterns
            context_text = ""
            if similar_patterns:
                context_text = "Ejemplos de preguntas similares y sus queries SQL:\n\n"
                for i, result in enumerate(similar_patterns, 1):
                    memory = result.memory
                    sql = memory.args.get("sql", "")
                    context_text += f"{i}. Pregunta: {memory.question}\n   SQL: {sql}\n\n"
            
            # Search for relevant DDL and documentation
            try:
                text_memories = await self.agent_memory.search_text_memories(
                    query=question,
                    context=context,
                    limit=5,
                    similarity_threshold=0.3,
                )
                
                if text_memories:
                    context_text += "\nDocumentación relevante:\n"
                    for mem in text_memories:
                        context_text += f"- {mem.memory.content[:500]}\n"
            except Exception as e:
                logger.warning(f"Error searching text memories: {e}")
            
            # Build system prompt for SQL generation
            system_prompt = SQL_GENERATION_SYSTEM
            if context_text:
                system_prompt += SQL_GENERATION_CONTEXT_TEMPLATE.format(context=context_text)
            
            # Create mock user for LLM request
            mock_user = User(
                id="system",
                username="coach_agent",
            )
            
            # Create LLM request
            request = LlmRequest(
                messages=[
                    LlmMessage(role="user", content=question),
                ],
                user=mock_user,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=1024,
            )
            
            # Send request to LLM
            response = await self.llm_service.send_request(request)
            
            if response.content:
                sql = response.content.strip()
                
                # Clean up SQL (remove markdown code blocks if present)
                if sql.startswith("```sql"):
                    sql = sql[6:]
                elif sql.startswith("```"):
                    sql = sql[3:]
                if sql.endswith("```"):
                    sql = sql[:-3]
                sql = sql.strip()
                
                logger.info(f"Generated SQL: {sql[:100]}...")
                
                return {
                    "success": True,
                    "sql": sql,
                    "error": None,
                    "similar_patterns": [
                        {"question": r.memory.question, "sql": r.memory.args.get("sql")}
                        for r in similar_patterns
                    ] if similar_patterns else None,
                }
            else:
                return {
                    "success": False,
                    "sql": None,
                    "error": "LLM did not return any content",
                    "similar_patterns": None,
                }

        except Exception as e:
            logger.error(f"Error generating SQL: {e}", exc_info=True)
            return {
                "success": False,
                "sql": None,
                "error": str(e),
                "similar_patterns": None,
            }

    async def add_training_data(
        self,
        ddl: str | None = None,
        documentation: str | None = None,
        question: str | None = None,
        sql: str | None = None,
    ) -> bool:
        """
        Add training data to agent memory.
        
        In Vanna 2.x, training data is stored as:
        - DDL/Documentation: Text memories (searchable context)
        - Question-SQL pairs: Tool usage patterns (for RAG)
        
        Args:
            ddl: DDL statement to add
            documentation: Documentation to add
            question: Question for question-SQL pair
            sql: SQL for question-SQL pair
            
        Returns:
            True if successful
        """
        try:
            # Create context for memory operations
            context = create_mock_context(self.agent_memory)
            
            if ddl:
                # Save DDL as text memory
                await self.agent_memory.save_text_memory(
                    content=f"DDL:\n{ddl}",
                    context=context,
                )
                logger.info("Added DDL training data")

            if documentation:
                # Save documentation as text memory
                await self.agent_memory.save_text_memory(
                    content=f"Documentation:\n{documentation}",
                    context=context,
                )
                logger.info("Added documentation training data")

            if question and sql:
                # Save question-SQL pair as tool usage pattern
                await self.agent_memory.save_tool_usage(
                    question=question,
                    tool_name="run_sql",
                    args={"sql": sql},
                    context=context,
                    success=True,
                    metadata={"type": "training"},
                )
                logger.info(f"Added question-SQL pair: {question[:50]}...")

            return True

        except Exception as e:
            logger.error(f"Error adding training data: {e}", exc_info=True)
            return False

    async def get_training_data(self) -> dict[str, Any]:
        """
        Get current training data statistics.
        
        Returns:
            {
                "ddl_count": int,
                "documentation_count": int,
                "sql_count": int
            }
        """
        try:
            # Create context for memory operations
            context = create_mock_context(self.agent_memory)
            
            # Get recent memories to count
            tool_memories = await self.agent_memory.get_recent_memories(
                context=context,
                limit=1000,
            )
            
            text_memories = await self.agent_memory.get_recent_text_memories(
                context=context,
                limit=1000,
            )
            
            # Count by type
            ddl_count = sum(1 for m in text_memories if m.content.startswith("DDL:"))
            doc_count = sum(1 for m in text_memories if m.content.startswith("Documentation:"))
            sql_count = len(tool_memories)
            
            return {
                "ddl_count": ddl_count,
                "documentation_count": doc_count,
                "sql_count": sql_count,
            }

        except Exception as e:
            logger.error(f"Error getting training data: {e}")
            return {
                "ddl_count": 0,
                "documentation_count": 0,
                "sql_count": 0,
            }


# Singleton instance
_vanna_service: VannaService | None = None


def get_vanna_service() -> VannaService:
    """Get or create the VannaService singleton."""
    global _vanna_service
    if _vanna_service is None:
        _vanna_service = VannaService()
    return _vanna_service

