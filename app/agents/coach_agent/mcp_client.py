"""
MCP Client for Coach Agent.

Connects to the Finanzas MCP Server using langchain-mcp-adapters.
"""

import os
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from app.config import settings


def get_mcp_server_path() -> str:
    """Get the path to the MCP server."""
    # Server is in finanzas-mcp-server/src/server.py relative to project root
    project_root = Path(__file__).parent.parent.parent.parent
    server_path = project_root / "finanzas-mcp-server" / "src" / "server.py"
    return str(server_path.absolute())


def create_mcp_client() -> MultiServerMCPClient:
    """
    Create MCP client configured for the Finanzas MCP Server.
    
    For development: Uses STDIO transport
    For production: Uses HTTP/SSE transport
    """
    # Get environment from settings
    is_production = settings.environment == "production"
    
    if is_production:
        # Production: Connect via HTTP
        mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8080/mcp")
        
        return MultiServerMCPClient({
            "finanzas": {
                "transport": "streamable_http",
                "url": mcp_url,
            }
        })
    else:
        # Development: Connect via STDIO
        server_path = get_mcp_server_path()
        
        return MultiServerMCPClient({
            "finanzas": {
                "command": "python",
                "args": [server_path],
                "transport": "stdio",
                "env": {
                    "OPENAI_API_KEY": settings.openai_api_key,
                    "POSTGRES_HOST": settings.postgres_host,
                    "POSTGRES_PORT": str(settings.postgres_port),
                    "POSTGRES_USER": settings.postgres_user,
                    "POSTGRES_PASSWORD": settings.postgres_password,
                    "POSTGRES_DB": settings.postgres_db,
                    "QDRANT_HOST": settings.qdrant_host,
                    "QDRANT_PORT": str(settings.qdrant_http_port),
                },
            }
        })


async def get_mcp_tools():
    """
    Load tools from the MCP server.
    
    Returns:
        List of LangChain tools from the MCP server
    """
    client = create_mcp_client()
    tools = await client.get_tools()
    return tools

