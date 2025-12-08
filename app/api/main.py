"""
FastAPI application entry point.

This is the main FastAPI application that handles:
- Twilio WhatsApp webhooks
- Health checks
- API routing
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health_router, webhook_router
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "application_starting",
        environment=settings.environment,
        twilio_configured=bool(settings.twilio_account_sid),
        llm_provider=settings.llm_provider
    )
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")


# Create FastAPI application
app = FastAPI(
    title="Finanzas Personales Inteligentes",
    description="WhatsApp-first personal finance assistant for Travel Mode",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Include Routers
# ─────────────────────────────────────────────────────────────────────────────

# API v1 routes
app.include_router(health_router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")

# Also mount health at root for simpler health checks
app.include_router(health_router)


# ─────────────────────────────────────────────────────────────────────────────
# Root Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "Finanzas Personales Inteligentes",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs" if settings.environment != "production" else None,
        "health": "/health",
        "webhook": "/api/v1/webhook/twilio"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Run with Uvicorn (for development)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level="debug" if settings.environment == "development" else "info",
    )

