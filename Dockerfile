# =============================================================================
# Dockerfile - Finanzas Personales Inteligentes
# Multi-stage build optimizado para producción
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Instalar dependencias con uv
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /app

# Instalar uv (gestor de paquetes rápido)
RUN pip install --no-cache-dir uv

# Copiar archivos necesarios para el build
COPY pyproject.toml uv.lock* README.md ./

# Crear entorno virtual e instalar dependencias de producción
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Imagen final ligera
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar entorno virtual del builder
COPY --from=builder /app/.venv /app/.venv

# Configurar PATH para usar el entorno virtual
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copiar código de la aplicación
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Puerto de la aplicación
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando de inicio
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
