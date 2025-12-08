"""
Date Utilities Tool.

Provides current date/time information for query construction.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def get_current_date(timezone: str = "UTC") -> dict[str, Any]:
    """
    Obtiene información de fecha y hora actual.
    
    Usa esta herramienta para obtener la fecha actual al construir queries con filtros de tiempo.
    Esto asegura filtros de fecha precisos (ej: "este mes", "última semana").
    
    Args:
        timezone: Nombre de timezone (default: "UTC")
                  Valores comunes: "UTC", "America/Mexico_City", "America/Lima"
    
    Returns:
        dict con:
        - date: str - Fecha actual (YYYY-MM-DD)
        - datetime: str - Fecha y hora actual (formato ISO)
        - timezone: str - Timezone usado
        - year: int - Año actual
        - month: int - Mes actual (1-12)
        - day: int - Día del mes
        - day_of_week: str - Nombre del día (Monday, Tuesday, etc.)
        - month_name: str - Nombre del mes (January, February, etc.)
        - week_of_year: int - Número de semana ISO
        - quarter: int - Trimestre (1-4)
        - first_day_of_month: str - Primer día del mes actual
        - last_day_of_month: str - Último día del mes actual
        - first_day_of_week: str - Lunes de la semana actual
    
    Example:
        get_current_date("America/Mexico_City")
        → {"date": "2024-12-03", "month": 12, "first_day_of_month": "2024-12-01", ...}
    """
    try:
        # Get timezone
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            logger.warning(f"Invalid timezone '{timezone}', using UTC")
            tz = ZoneInfo("UTC")
            timezone = "UTC"

        now = datetime.now(tz)

        # Calculate useful dates
        first_day_of_month = now.replace(day=1)

        # Last day of month
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        last_day_of_month = next_month - timedelta(days=1)

        # Monday of current week
        days_since_monday = now.weekday()
        first_day_of_week = now - timedelta(days=days_since_monday)

        # Quarter
        quarter = (now.month - 1) // 3 + 1

        result = {
            "date": now.strftime("%Y-%m-%d"),
            "datetime": now.isoformat(),
            "timezone": timezone,
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "day_of_week": now.strftime("%A"),
            "month_name": now.strftime("%B"),
            "week_of_year": now.isocalendar()[1],
            "quarter": quarter,
            "first_day_of_month": first_day_of_month.strftime("%Y-%m-%d"),
            "last_day_of_month": last_day_of_month.strftime("%Y-%m-%d"),
            "first_day_of_week": first_day_of_week.strftime("%Y-%m-%d"),
        }

        logger.info(f"Current date: {result['date']} ({timezone})")

        return result

    except Exception as e:
        logger.error(f"Error getting current date: {e}")
        # Return basic UTC fallback
        now = datetime.utcnow()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "datetime": now.isoformat(),
            "timezone": "UTC",
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "day_of_week": now.strftime("%A"),
            "month_name": now.strftime("%B"),
            "week_of_year": now.isocalendar()[1],
            "quarter": (now.month - 1) // 3 + 1,
            "first_day_of_month": now.replace(day=1).strftime("%Y-%m-%d"),
            "last_day_of_month": "",
            "first_day_of_week": "",
        }

