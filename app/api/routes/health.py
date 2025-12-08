"""
Health check endpoints for monitoring and deployment.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    environment: str
    checks: dict[str, bool]


class ReadinessStatus(BaseModel):
    """Readiness check response model."""
    ready: bool
    checks: dict[str, dict]


@router.get("", response_model=HealthStatus)
@router.get("/", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Basic health check endpoint.
    
    Returns basic application status without checking dependencies.
    Used by load balancers for simple alive checks.
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="0.1.0",
        environment=settings.environment,
        checks={"app": True}
    )


@router.get("/ready", response_model=ReadinessStatus)
async def readiness_check(db: Session = Depends(get_db)) -> ReadinessStatus:
    """
    Readiness check with dependency verification.
    
    Checks database connectivity and other critical services.
    Used by orchestrators to determine if traffic can be routed.
    """
    checks = {}
    all_ready = True
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": None}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        all_ready = False
        logger.error("health_check_db_failed", error=str(e))
    
    # Check Twilio configuration
    twilio_configured = bool(
        settings.twilio_account_sid and settings.twilio_auth_token
    )
    checks["twilio"] = {
        "status": "ok" if twilio_configured else "not_configured",
        "configured": twilio_configured
    }
    
    # Check LLM provider configuration
    llm_configured = bool(settings.openai_api_key)
    checks["llm"] = {
        "status": "ok" if llm_configured else "not_configured",
        "provider": settings.llm_provider,
        "configured": llm_configured
    }
    
    return ReadinessStatus(
        ready=all_ready,
        checks=checks
    )


@router.get("/live")
async def liveness_check() -> dict:
    """
    Simple liveness probe.
    
    Returns 200 if the application process is running.
    Used by Kubernetes/Docker for container health.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

