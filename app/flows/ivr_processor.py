"""
IVR Processor.

Handles menu-based (IVR) configuration flows without LLM calls.
Provides conversational flow for onboarding, budget, trip, and card setup.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.flows.constants import (
    SUPPORTED_CURRENCIES,
    SUPPORTED_COUNTRIES,
    COUNTRY_TIMEZONES,
    CURRENCY_NAMES,
    CONFIRM_KEYWORDS,
    DENY_KEYWORDS,
)
from app.flows.validators import (
    validate_name,
    validate_currency,
    validate_country,
    validate_timezone,
    validate_amount,
    validate_date,
    validate_confirmation,
)
from app.logging_config import get_logger
from app.models.user import User

logger = get_logger(__name__)


@dataclass
class IVRResponse:
    """Response from IVR processor."""
    message: str
    next_step: str | None = None
    flow_complete: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class IVRProcessor:
    """
    Processes IVR flows without LLM.
    
    Handles step-by-step configuration flows using menu-based interactions.
    """

    def __init__(self, db: Session):
        """
        Initialize IVR processor.
        
        Args:
            db: Database session for persistence
        """
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # Onboarding Flow
    # ─────────────────────────────────────────────────────────────────────────

    def process_onboarding(
        self,
        user: User,
        current_step: str | None,
        user_input: str,
    ) -> IVRResponse:
        """
        Process a step in the onboarding flow.
        
        Flow: name -> currency -> country -> timezone -> confirm
        
        Args:
            user: User model to update
            current_step: Current step in the flow
            user_input: User's input text
            
        Returns:
            IVRResponse with message and next step
        """
        logger.debug(
            "ivr_process_onboarding",
            user_id=str(user.id),
            current_step=current_step,
            input_preview=user_input[:50] if user_input else None,
        )

        # If no step, start onboarding
        if not current_step or current_step == "start":
            return self._start_onboarding(user)

        # Process based on current step
        if current_step == "name":
            return self._process_name(user, user_input)
        elif current_step == "currency":
            return self._process_currency(user, user_input)
        elif current_step == "country":
            return self._process_country(user, user_input)
        elif current_step == "timezone":
            return self._process_timezone(user, user_input)
        elif current_step == "confirm":
            return self._process_confirmation(user, user_input)
        else:
            # Unknown step, restart
            return self._start_onboarding(user)

    def _start_onboarding(self, user: User) -> IVRResponse:
        """Start the onboarding flow."""
        user.onboarding_status = "in_progress"
        user.onboarding_step = "name"
        self.db.commit()

        return IVRResponse(
            message=(
                "👋 ¡Hola! Soy tu asistente de finanzas personales.\n\n"
                "Te ayudaré a controlar tus gastos y presupuestos.\n\n"
                "Para comenzar, ¿cuál es tu nombre?"
            ),
            next_step="name"
        )

    def _process_name(self, user: User, user_input: str) -> IVRResponse:
        """Process name input."""
        result = validate_name(user_input)
        
        if not result.valid:
            return IVRResponse(
                message=f"❌ {result.error}\n\n¿Cuál es tu nombre?",
                next_step="name",
                error=result.error
            )
        
        # Save name
        user.full_name = result.value
        user.nickname = result.value.split()[0]  # First name as nickname
        user.onboarding_step = "currency"
        self.db.commit()
        
        return IVRResponse(
            message=self._build_currency_menu(result.value),
            next_step="currency",
            data={"name": result.value}
        )

    def _process_currency(self, user: User, user_input: str) -> IVRResponse:
        """Process currency selection."""
        result = validate_currency(user_input)
        
        if not result.valid:
            return IVRResponse(
                message=f"❌ {result.error}\n\n{self._build_currency_menu(user.display_name)}",
                next_step="currency",
                error=result.error
            )
        
        # Save currency
        user.home_currency = result.value
        user.onboarding_step = "country"
        self.db.commit()
        
        currency_name = CURRENCY_NAMES.get(result.value, result.value)
        return IVRResponse(
            message=f"✅ Moneda: *{result.value}* ({currency_name})\n\n{self._build_country_menu()}",
            next_step="country",
            data={"currency": result.value}
        )

    def _process_country(self, user: User, user_input: str) -> IVRResponse:
        """Process country selection."""
        result = validate_country(user_input)
        
        if not result.valid:
            return IVRResponse(
                message=f"❌ {result.error}\n\n{self._build_country_menu()}",
                next_step="country",
                error=result.error
            )
        
        # Save country
        user.country = result.value
        user.onboarding_step = "timezone"
        self.db.commit()
        
        country_name = SUPPORTED_COUNTRIES.get(result.value, result.value)
        return IVRResponse(
            message=f"✅ País: *{country_name}*\n\n{self._build_timezone_prompt(result.value)}",
            next_step="timezone",
            data={"country": result.value}
        )

    def _process_timezone(self, user: User, user_input: str) -> IVRResponse:
        """Process timezone selection."""
        result = validate_timezone(user_input, user.country)
        
        # Timezone validation is always valid (uses defaults)
        user.timezone = result.value
        user.onboarding_step = "confirm"
        self.db.commit()
        
        return IVRResponse(
            message=self._build_confirmation_message(user),
            next_step="confirm",
            data={"timezone": result.value}
        )

    def _process_confirmation(self, user: User, user_input: str) -> IVRResponse:
        """Process onboarding confirmation."""
        text = user_input.strip().lower()
        
        if text in CONFIRM_KEYWORDS:
            # Complete onboarding
            user.onboarding_status = "completed"
            user.onboarding_step = None
            user.onboarding_completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(
                "onboarding_completed",
                user_id=str(user.id),
                currency=user.home_currency,
                country=user.country,
            )
            
            return IVRResponse(
                message=self._build_welcome_message(user),
                flow_complete=True,
                data={
                    "name": user.full_name,
                    "currency": user.home_currency,
                    "country": user.country,
                    "timezone": user.timezone,
                }
            )
        
        elif text in DENY_KEYWORDS:
            # Restart onboarding
            user.onboarding_step = "name"
            self.db.commit()
            
            return IVRResponse(
                message="🔄 Vamos a empezar de nuevo.\n\n¿Cuál es tu nombre?",
                next_step="name"
            )
        
        else:
            return IVRResponse(
                message=(
                    "❓ No entendí tu respuesta.\n\n"
                    "Responde *1* para confirmar o *2* para empezar de nuevo."
                ),
                next_step="confirm"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Menu Builders
    # ─────────────────────────────────────────────────────────────────────────

    def _build_currency_menu(self, name: str) -> str:
        """Build currency selection menu."""
        lines = [f"¡Perfecto, {name}! 👋", "", "💰 ¿Cuál es tu moneda principal?", ""]
        
        for i, curr in enumerate(SUPPORTED_CURRENCIES, 1):
            currency_name = CURRENCY_NAMES.get(curr, "")
            lines.append(f"{i}. {curr} - {currency_name}")
        
        lines.append("")
        lines.append("_Responde con el número o el código (ej: USD)_")
        
        return "\n".join(lines)

    def _build_country_menu(self) -> str:
        """Build country selection menu."""
        lines = ["🌎 ¿En qué país estás?", ""]
        
        for i, (code, name) in enumerate(SUPPORTED_COUNTRIES.items(), 1):
            lines.append(f"{i}. {name}")
        
        lines.append("")
        lines.append("_Responde con el número o nombre del país_")
        
        return "\n".join(lines)

    def _build_timezone_prompt(self, country: str) -> str:
        """Build timezone selection prompt."""
        default_tz = COUNTRY_TIMEZONES.get(country, "America/Mexico_City")
        
        return (
            f"🕐 Zona horaria\n\n"
            f"Responde *1* para usar: {default_tz} _(recomendado)_\n\n"
            f"O escribe tu timezone si es diferente\n"
            f"_(ej: America/Bogota, America/Lima)_"
        )

    def _build_confirmation_message(self, user: User) -> str:
        """Build confirmation message with user details."""
        country_name = SUPPORTED_COUNTRIES.get(user.country, user.country or "N/A")
        currency_name = CURRENCY_NAMES.get(user.home_currency, user.home_currency)
        
        return (
            f"📋 *Confirma tu configuración:*\n\n"
            f"• Nombre: {user.full_name}\n"
            f"• Moneda: {user.home_currency} ({currency_name})\n"
            f"• País: {country_name}\n"
            f"• Timezone: {user.timezone}\n\n"
            f"¿Todo correcto?\n"
            f"*1.* Sí, confirmar\n"
            f"*2.* No, empezar de nuevo"
        )

    def _build_welcome_message(self, user: User) -> str:
        """Build welcome message after onboarding completion."""
        return (
            f"✅ ¡Listo, {user.display_name}! Tu cuenta está configurada.\n\n"
            f"Ahora puedes:\n\n"
            f"💰 *Registrar gastos*\n"
            f"   Escribe: \"50000 en almuerzo\"\n\n"
            f"📊 *Crear presupuesto*\n"
            f"   Escribe: \"crear presupuesto\"\n\n"
            f"✈️ *Configurar viaje*\n"
            f"   Escribe: \"nuevo viaje\"\n\n"
            f"💳 *Agregar tarjeta*\n"
            f"   Escribe: \"configurar tarjeta\"\n\n"
            f"❓ *Ayuda*\n"
            f"   Escribe: \"ayuda\" o \"menu\""
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Budget Flow
    # ─────────────────────────────────────────────────────────────────────────

    def process_budget_creation(
        self,
        user: User,
        current_step: str | None,
        user_input: str,
        temp_data: dict[str, Any] | None = None,
    ) -> IVRResponse:
        """
        Process budget creation flow.
        
        Flow: name -> amount -> currency -> start_date -> end_date -> confirm
        
        Args:
            user: User model
            current_step: Current step in the flow
            user_input: User's input text
            temp_data: Accumulated data from previous steps
            
        Returns:
            IVRResponse with next step or completion
        """
        if temp_data is None:
            temp_data = {}
        
        logger.debug(
            "ivr_process_budget",
            user_id=str(user.id),
            current_step=current_step,
        )
        
        # If no step, start budget creation
        if not current_step or current_step == "start":
            return self._start_budget_creation(temp_data)
        
        # Process based on current step
        if current_step == "name":
            return self._process_budget_name(user, user_input, temp_data)
        elif current_step == "amount":
            return self._process_budget_amount(user, user_input, temp_data)
        elif current_step == "currency":
            return self._process_budget_currency(user, user_input, temp_data)
        elif current_step == "start_date":
            return self._process_budget_start_date(user, user_input, temp_data)
        elif current_step == "end_date":
            return self._process_budget_end_date(user, user_input, temp_data)
        elif current_step == "confirm":
            return self._process_budget_confirmation(user, user_input, temp_data)
        else:
            # Unknown step, restart
            return self._start_budget_creation(temp_data)
    
    def _start_budget_creation(self, temp_data: dict[str, Any]) -> IVRResponse:
        """Start the budget creation flow."""
        return IVRResponse(
            message=(
                "💰 *Crear nuevo presupuesto*\n\n"
                "¿Cómo quieres llamar a este presupuesto?\n\n"
                "_Ejemplo: \"Enero 2025\" o \"Vacaciones\"_"
            ),
            next_step="name",
            data=temp_data,
        )
    
    def _process_budget_name(
        self, user: User, user_input: str, temp_data: dict[str, Any]
    ) -> IVRResponse:
        """Process budget name input."""
        result = validate_name(user_input)
        
        if not result.valid:
            return IVRResponse(
                message=f"❌ {result.error}\n\n¿Cómo quieres llamar al presupuesto?",
                next_step="name",
                error=result.error,
                data=temp_data,
            )
        
        temp_data["name"] = result.value
        
        return IVRResponse(
            message=(
                f"✅ Nombre: *{result.value}*\n\n"
                f"💵 ¿Cuál es el monto total del presupuesto?\n\n"
                f"_Ejemplo: 5000000 o 3000_"
            ),
            next_step="amount",
            data=temp_data,
        )
    
    def _process_budget_amount(
        self, user: User, user_input: str, temp_data: dict[str, Any]
    ) -> IVRResponse:
        """Process budget amount input."""
        result = validate_amount(user_input)
        
        if not result.valid:
            return IVRResponse(
                message=f"❌ {result.error}\n\n¿Cuál es el monto total del presupuesto?",
                next_step="amount",
                error=result.error,
                data=temp_data,
            )
        
        temp_data["amount"] = str(result.value)
        
        # Check if we should use user's home currency by default
        return IVRResponse(
            message=self._build_budget_currency_menu(user, result.value),
            next_step="currency",
            data=temp_data,
        )
    
    def _process_budget_currency(
        self, user: User, user_input: str, temp_data: dict[str, Any]
    ) -> IVRResponse:
        """Process budget currency selection."""
        text = user_input.strip()
        
        # Option 1: Use home currency
        if text == "1":
            currency = user.home_currency
        else:
            result = validate_currency(text)
            if not result.valid:
                return IVRResponse(
                    message=f"❌ {result.error}\n\n{self._build_budget_currency_menu(user, temp_data.get('amount', '0'))}",
                    next_step="currency",
                    error=result.error,
                    data=temp_data,
                )
            currency = result.value
        
        temp_data["currency"] = currency
        currency_name = CURRENCY_NAMES.get(currency, currency)
        
        return IVRResponse(
            message=(
                f"✅ Moneda: *{currency}* ({currency_name})\n\n"
                f"📅 ¿Cuándo inicia el presupuesto?\n\n"
                f"Responde *1* para hoy\n"
                f"O escribe la fecha (DD/MM/YYYY)"
            ),
            next_step="start_date",
            data=temp_data,
        )
    
    def _process_budget_start_date(
        self, user: User, user_input: str, temp_data: dict[str, Any]
    ) -> IVRResponse:
        """Process budget start date."""
        text = user_input.strip()
        
        # Option 1: Today
        if text == "1":
            from datetime import date
            start_date = date.today()
        else:
            result = validate_date(text)
            if not result.valid:
                return IVRResponse(
                    message=(
                        f"❌ {result.error}\n\n"
                        f"📅 ¿Cuándo inicia el presupuesto?\n"
                        f"Responde *1* para hoy o escribe la fecha (DD/MM/YYYY)"
                    ),
                    next_step="start_date",
                    error=result.error,
                    data=temp_data,
                )
            start_date = result.value
        
        temp_data["start_date"] = start_date.isoformat()
        
        return IVRResponse(
            message=(
                f"✅ Inicio: *{start_date.strftime('%d/%m/%Y')}*\n\n"
                f"📅 ¿Cuándo termina el presupuesto?\n\n"
                f"Responde *1* para fin de mes\n"
                f"Responde *2* para 30 días desde hoy\n"
                f"O escribe la fecha (DD/MM/YYYY)"
            ),
            next_step="end_date",
            data=temp_data,
        )
    
    def _process_budget_end_date(
        self, user: User, user_input: str, temp_data: dict[str, Any]
    ) -> IVRResponse:
        """Process budget end date."""
        from datetime import date, timedelta
        import calendar
        
        text = user_input.strip()
        today = date.today()
        
        # Option 1: End of month
        if text == "1":
            _, last_day = calendar.monthrange(today.year, today.month)
            end_date = date(today.year, today.month, last_day)
        # Option 2: 30 days from today
        elif text == "2":
            end_date = today + timedelta(days=30)
        else:
            result = validate_date(text)
            if not result.valid:
                return IVRResponse(
                    message=(
                        f"❌ {result.error}\n\n"
                        f"📅 ¿Cuándo termina el presupuesto?\n"
                        f"Responde *1* para fin de mes, *2* para 30 días, o escribe fecha"
                    ),
                    next_step="end_date",
                    error=result.error,
                    data=temp_data,
                )
            end_date = result.value
        
        temp_data["end_date"] = end_date.isoformat()
        
        return IVRResponse(
            message=self._build_budget_confirmation(temp_data),
            next_step="confirm",
            data=temp_data,
        )
    
    def _process_budget_confirmation(
        self, user: User, user_input: str, temp_data: dict[str, Any]
    ) -> IVRResponse:
        """Process budget creation confirmation."""
        text = user_input.strip().lower()
        
        if text in CONFIRM_KEYWORDS:
            # Create the budget
            try:
                budget = self._create_budget_from_data(user, temp_data)
                
                logger.info(
                    "budget_created_via_ivr",
                    user_id=str(user.id),
                    budget_id=str(budget.id),
                    amount=temp_data.get("amount"),
                    currency=temp_data.get("currency"),
                )
                
                return IVRResponse(
                    message=(
                        f"✅ ¡Presupuesto *{temp_data.get('name')}* creado!\n\n"
                        f"💰 Monto: {temp_data.get('amount')} {temp_data.get('currency')}\n"
                        f"📅 Periodo: {temp_data.get('start_date')} - {temp_data.get('end_date')}\n\n"
                        f"Este presupuesto está ahora activo. Los gastos que registres "
                        f"se descontarán automáticamente.\n\n"
                        f"Puedes registrar gastos escribiendo algo como:\n"
                        f"\"50000 en almuerzo\" o \"25 dólares taxi\""
                    ),
                    flow_complete=True,
                    data={"budget_id": str(budget.id)},
                )
            except Exception as e:
                logger.error("budget_creation_failed", error=str(e), exc_info=True)
                return IVRResponse(
                    message=f"❌ Error al crear el presupuesto: {str(e)}",
                    next_step="confirm",
                    error=str(e),
                    data=temp_data,
                )
        
        elif text in DENY_KEYWORDS:
            # Cancel and restart
            return IVRResponse(
                message="❌ Presupuesto cancelado.\n\n¿Qué deseas hacer?\n\nEscribe \"crear presupuesto\" para intentar de nuevo.",
                flow_complete=True,
            )
        
        else:
            return IVRResponse(
                message=(
                    "❓ No entendí tu respuesta.\n\n"
                    "Responde *1* para confirmar o *2* para cancelar."
                ),
                next_step="confirm",
                data=temp_data,
            )
    
    def _build_budget_currency_menu(self, user: User, amount: Any) -> str:
        """Build currency selection menu for budget."""
        home_currency = user.home_currency
        home_name = CURRENCY_NAMES.get(home_currency, "")
        
        lines = [
            f"💰 Presupuesto: *{amount}*",
            "",
            "¿En qué moneda?",
            "",
            f"*1.* {home_currency} - {home_name} _(tu moneda base)_",
        ]
        
        # Add other currencies
        idx = 2
        for curr in SUPPORTED_CURRENCIES:
            if curr != home_currency:
                currency_name = CURRENCY_NAMES.get(curr, "")
                lines.append(f"{idx}. {curr} - {currency_name}")
                idx += 1
        
        lines.append("")
        lines.append("_Responde con el número o código (ej: USD)_")
        
        return "\n".join(lines)
    
    def _build_budget_confirmation(self, temp_data: dict[str, Any]) -> str:
        """Build confirmation message for budget."""
        currency_name = CURRENCY_NAMES.get(temp_data.get("currency", ""), "")
        
        return (
            f"📋 *Confirma tu presupuesto:*\n\n"
            f"• Nombre: {temp_data.get('name')}\n"
            f"• Monto: {temp_data.get('amount')} {temp_data.get('currency')} ({currency_name})\n"
            f"• Inicio: {temp_data.get('start_date')}\n"
            f"• Fin: {temp_data.get('end_date')}\n\n"
            f"¿Crear este presupuesto?\n"
            f"*1.* Sí, crear\n"
            f"*2.* No, cancelar"
        )
    
    def _create_budget_from_data(self, user: User, temp_data: dict[str, Any]):
        """Create budget from accumulated data."""
        from datetime import date
        from decimal import Decimal
        from app.storage.budget_writer import create_budget_and_set_current
        
        start_date = date.fromisoformat(temp_data["start_date"])
        end_date = date.fromisoformat(temp_data["end_date"])
        amount = Decimal(temp_data["amount"])
        
        budget = create_budget_and_set_current(
            db=self.db,
            user=user,
            name=temp_data["name"],
            amount=amount,
            currency=temp_data["currency"],
            start_date=start_date,
            end_date=end_date,
        )
        
        return budget

    # ─────────────────────────────────────────────────────────────────────────
    # Trip Creation Flow
    # ─────────────────────────────────────────────────────────────────────────

    def process_trip_creation(
        self,
        user: User,
        current_step: str | None,
        user_input: str,
        temp_data: dict[str, Any] | None = None,
    ) -> IVRResponse:
        """
        Process trip creation flow.
        
        Flow: name -> country -> start_date -> end_date -> link_budget -> budget_amount -> confirm
        
        Args:
            user: User model
            current_step: Current step in the flow
            user_input: User's input text
            temp_data: Accumulated data from previous steps
            
        Returns:
            IVRResponse with message and next step
        """
        logger.debug(
            "ivr_process_trip",
            user_id=str(user.id),
            current_step=current_step,
            input_preview=user_input[:50] if user_input else None,
        )
        
        temp_data = temp_data or {}
        text = user_input.strip().lower()
        
        # Start flow
        if not current_step or current_step == "start":
            return IVRResponse(
                message=(
                    "✈️ *Nuevo viaje*\n\n"
                    "¿Cómo quieres llamar a este viaje?\n\n"
                    "_Ejemplo: Vacaciones Ecuador, Trabajo CDMX, Europa 2026_"
                ),
                next_step="name",
                data=temp_data,
            )
        
        # Step: Name
        if current_step == "name":
            result = validate_name(user_input)
            if not result.valid:
                return IVRResponse(
                    message=f"❌ {result.error}\n\n¿Cómo quieres llamar al viaje?",
                    next_step="name",
                    data=temp_data,
                )
            
            temp_data["name"] = result.value
            return IVRResponse(
                message=self._build_country_menu_for_trip(result.value),
                next_step="country",
                data=temp_data,
            )
        
        # Step: Country
        if current_step == "country":
            result = validate_country(user_input)
            if not result.valid:
                return IVRResponse(
                    message=f"❌ {result.error}\n\n{self._build_country_menu_for_trip(temp_data.get('name', ''))}",
                    next_step="country",
                    data=temp_data,
                )
            
            temp_data["country"] = result.value
            country_name = SUPPORTED_COUNTRIES.get(result.value, result.value)
            
            return IVRResponse(
                message=(
                    f"✈️ {temp_data['name']} → *{country_name}*\n\n"
                    f"📅 ¿Cuándo empieza el viaje?\n\n"
                    f"_Ejemplo: 15/02/2026 o \"hoy\"_"
                ),
                next_step="start_date",
                data=temp_data,
            )
        
        # Step: Start Date
        if current_step == "start_date":
            result = validate_date(user_input)
            if not result.valid:
                return IVRResponse(
                    message=f"❌ {result.error}\n\n¿Cuándo empieza el viaje?",
                    next_step="start_date",
                    data=temp_data,
                )
            
            temp_data["start_date"] = result.value.isoformat()
            
            return IVRResponse(
                message=(
                    f"📅 Inicio: *{result.value.strftime('%d/%m/%Y')}*\n\n"
                    f"¿Cuándo termina el viaje?\n\n"
                    f"_Ejemplo: 28/02/2026 o \"1 semana\"_"
                ),
                next_step="end_date",
                data=temp_data,
            )
        
        # Step: End Date
        if current_step == "end_date":
            result = validate_date(user_input)
            if not result.valid:
                return IVRResponse(
                    message=f"❌ {result.error}\n\n¿Cuándo termina el viaje?",
                    next_step="end_date",
                    data=temp_data,
                )
            
            temp_data["end_date"] = result.value.isoformat()
            
            # Ask about budget linking
            return IVRResponse(
                message=self._build_budget_linking_menu(user, temp_data),
                next_step="link_budget",
                data=temp_data,
            )
        
        # Step: Link Budget
        if current_step == "link_budget":
            return self._process_budget_linking(user, user_input, temp_data)
        
        # Step: Budget Amount (if creating new)
        if current_step == "budget_amount":
            result = validate_amount(user_input)
            if not result.valid:
                return IVRResponse(
                    message=f"❌ {result.error}\n\n¿Cuál es el presupuesto para el viaje?",
                    next_step="budget_amount",
                    data=temp_data,
                )
            
            temp_data["budget_amount"] = str(result.value)
            temp_data["budget_currency"] = user.home_currency
            
            return IVRResponse(
                message=self._build_trip_confirmation(user, temp_data),
                next_step="confirm",
                data=temp_data,
            )
        
        # Step: Confirm
        if current_step == "confirm":
            if text in CONFIRM_KEYWORDS:
                try:
                    trip, budget = self._create_trip_with_budget(user, temp_data)
                    
                    budget_msg = ""
                    if budget:
                        budget_msg = f"\n💰 Presupuesto: {budget.name} ({budget.total_amount:,.0f} {budget.currency})"
                    
                    country_name = SUPPORTED_COUNTRIES.get(temp_data.get("country", ""), "")
                    
                    return IVRResponse(
                        message=(
                            f"✅ ¡Viaje creado!\n\n"
                            f"✈️ *{trip.name}*\n"
                            f"• Destino: {country_name}\n"
                            f"• Inicio: {trip.start_date.strftime('%d/%m/%Y')}\n"
                            f"• Fin: {trip.end_date.strftime('%d/%m/%Y') if trip.end_date else 'Sin definir'}"
                            f"{budget_msg}\n\n"
                            f"🎒 *Modo viaje activado*\n"
                            f"Tus gastos se registrarán en este viaje."
                        ),
                        flow_complete=True,
                        data={"trip_id": str(trip.id)},
                    )
                except Exception as e:
                    logger.error("trip_creation_failed", error=str(e), exc_info=True)
                    return IVRResponse(
                        message=f"❌ Error creando viaje: {str(e)}",
                        flow_complete=True,
                    )
            
            elif text in DENY_KEYWORDS:
                return IVRResponse(
                    message=(
                        "❌ Viaje cancelado.\n\n"
                        "Escribe \"nuevo viaje\" para intentar de nuevo."
                    ),
                    flow_complete=True,
                )
            
            else:
                return IVRResponse(
                    message=(
                        "❓ No entendí.\n\n"
                        "Responde *1* para confirmar o *2* para cancelar."
                    ),
                    next_step="confirm",
                    data=temp_data,
                )
        
        # Default: start over
        return IVRResponse(
            message="✈️ Escribe \"nuevo viaje\" para crear un viaje.",
            flow_complete=True,
        )
    
    def _build_country_menu_for_trip(self, trip_name: str) -> str:
        """Build country selection menu for trip."""
        lines = [
            f"✈️ *{trip_name}*",
            "",
            "🌎 ¿A qué país viajas?",
            "",
        ]
        
        for i, (code, name) in enumerate(SUPPORTED_COUNTRIES.items(), 1):
            lines.append(f"*{i}.* {name}")
        
        lines.append("")
        lines.append("_Responde con el número o nombre del país_")
        
        return "\n".join(lines)
    
    def _build_budget_linking_menu(self, user: User, temp_data: dict[str, Any]) -> str:
        """Build budget linking options menu."""
        from app.storage.budget_writer import get_user_active_budgets
        
        country_name = SUPPORTED_COUNTRIES.get(temp_data.get("country", ""), "")
        
        lines = [
            f"✈️ {temp_data['name']} → {country_name}",
            f"📅 {temp_data['start_date']} - {temp_data['end_date']}",
            "",
            "💰 *¿Qué presupuesto usar?*",
            "",
            "*1.* Crear nuevo presupuesto para el viaje",
            "*2.* Sin presupuesto (registrar gastos sin límite)",
        ]
        
        # Get existing active budgets
        try:
            existing_budgets = get_user_active_budgets(self.db, user.id)
            if existing_budgets:
                lines.append("")
                lines.append("_O usar un presupuesto existente:_")
                for i, budget in enumerate(existing_budgets, 3):
                    remaining = budget.total_amount - (budget.spent_amount or 0)
                    lines.append(
                        f"{i}. {budget.name} ({remaining:,.0f} {budget.currency} disponible)"
                    )
                temp_data["existing_budgets"] = [
                    {"id": str(b.id), "name": b.name} for b in existing_budgets
                ]
        except Exception as e:
            logger.warning("get_budgets_failed", error=str(e))
        
        return "\n".join(lines)
    
    def _process_budget_linking(
        self,
        user: User,
        user_input: str,
        temp_data: dict[str, Any]
    ) -> IVRResponse:
        """Process budget linking choice."""
        text = user_input.strip()
        
        # Option 1: Create new budget
        if text == "1" or "nuevo" in text.lower() or "crear" in text.lower():
            temp_data["budget_action"] = "create"
            return IVRResponse(
                message=(
                    f"💰 *Presupuesto para {temp_data['name']}*\n\n"
                    f"¿Cuál es el monto total del presupuesto?\n\n"
                    f"_Ejemplo: 5000000 (en {user.home_currency})_"
                ),
                next_step="budget_amount",
                data=temp_data,
            )
        
        # Option 2: No budget
        elif text == "2" or "sin" in text.lower():
            temp_data["budget_action"] = "none"
            return IVRResponse(
                message=self._build_trip_confirmation(user, temp_data),
                next_step="confirm",
                data=temp_data,
            )
        
        # Option 3+: Link existing budget
        else:
            try:
                choice = int(text)
                existing_budgets = temp_data.get("existing_budgets", [])
                
                if 3 <= choice <= len(existing_budgets) + 2:
                    budget_info = existing_budgets[choice - 3]
                    temp_data["budget_action"] = "link"
                    temp_data["linked_budget_id"] = budget_info["id"]
                    temp_data["linked_budget_name"] = budget_info["name"]
                    
                    return IVRResponse(
                        message=self._build_trip_confirmation(user, temp_data),
                        next_step="confirm",
                        data=temp_data,
                    )
            except (ValueError, IndexError):
                pass
            
            return IVRResponse(
                message=(
                    "❌ Opción no válida.\n\n"
                    "*1.* Crear nuevo presupuesto\n"
                    "*2.* Sin presupuesto"
                ),
                next_step="link_budget",
                data=temp_data,
            )
    
    def _build_trip_confirmation(self, user: User, temp_data: dict[str, Any]) -> str:
        """Build confirmation message for trip."""
        country_name = SUPPORTED_COUNTRIES.get(temp_data.get("country", ""), "")
        
        budget_line = ""
        action = temp_data.get("budget_action", "none")
        
        if action == "create":
            amount = temp_data.get("budget_amount", "0")
            currency = temp_data.get("budget_currency", user.home_currency)
            budget_line = f"• Presupuesto: Nuevo ({amount} {currency})\n"
        elif action == "link":
            budget_name = temp_data.get("linked_budget_name", "")
            budget_line = f"• Presupuesto: {budget_name}\n"
        else:
            budget_line = "• Presupuesto: Sin presupuesto\n"
        
        return (
            f"📋 *Confirma tu viaje:*\n\n"
            f"• Nombre: {temp_data.get('name')}\n"
            f"• Destino: {country_name}\n"
            f"• Inicio: {temp_data.get('start_date')}\n"
            f"• Fin: {temp_data.get('end_date')}\n"
            f"{budget_line}\n"
            f"¿Crear este viaje?\n"
            f"*1.* Sí, crear\n"
            f"*2.* No, cancelar"
        )
    
    def _create_trip_with_budget(self, user: User, temp_data: dict[str, Any]):
        """Create trip and optionally create/link budget."""
        from datetime import date as date_type
        from decimal import Decimal
        from uuid import UUID as UUIDType
        
        from app.storage.trip_writer import create_trip
        from app.storage.budget_writer import create_budget_and_set_current, link_budget_to_trip
        
        start_date = date_type.fromisoformat(temp_data["start_date"])
        end_date = date_type.fromisoformat(temp_data["end_date"])
        
        # Create the trip
        trip_result = create_trip(
            db=self.db,
            user_id=user.id,
            name=temp_data["name"],
            start_date=start_date,
            end_date=end_date,
            destination_country=temp_data["country"],
            set_as_current=True,
        )
        
        if not trip_result.success:
            raise Exception(trip_result.error)
        
        trip = trip_result.trip
        budget = None
        
        # Handle budget action
        action = temp_data.get("budget_action", "none")
        
        if action == "create":
            # Create new budget for the trip
            amount = Decimal(temp_data.get("budget_amount", "0"))
            currency = temp_data.get("budget_currency", user.home_currency)
            
            budget = create_budget_and_set_current(
                db=self.db,
                user=user,
                name=f"Presupuesto {temp_data['name']}",
                amount=amount,
                currency=currency,
                start_date=start_date,
                end_date=end_date,
                trip_id=trip.id,
            )
            
        elif action == "link":
            # Link existing budget to trip
            budget_id = UUIDType(temp_data["linked_budget_id"])
            budget = link_budget_to_trip(self.db, budget_id, trip.id)
        
        return trip, budget

    # ─────────────────────────────────────────────────────────────────────────
    # Card Configuration Flow
    # ─────────────────────────────────────────────────────────────────────────

    def process_card_configuration(
        self,
        user: User,
        current_step: str | None,
        user_input: str,
        temp_data: dict[str, Any] | None = None,
    ) -> IVRResponse:
        """
        Process card configuration flow.
        
        Flow: name -> type -> network -> last_four -> color -> confirm
        
        Args:
            user: User model
            current_step: Current step in the flow
            user_input: User's input text
            temp_data: Accumulated data from previous steps
            
        Returns:
            IVRResponse with message and next step
        """
        from app.flows.constants import CARD_TYPES, CARD_NETWORKS, CARD_COLORS
        
        logger.debug(
            "ivr_process_card",
            user_id=str(user.id),
            current_step=current_step,
            input_preview=user_input[:50] if user_input else None,
        )
        
        temp_data = temp_data or {}
        text = user_input.strip().lower()
        
        # Start flow
        if not current_step or current_step == "start":
            return IVRResponse(
                message=(
                    "💳 *Configurar nueva tarjeta*\n\n"
                    "¿Cómo quieres llamar a esta tarjeta?\n\n"
                    "_Ejemplo: Visa Gold, Mastercard Viajes, Débito Nómina_"
                ),
                next_step="name",
                data=temp_data,
            )
        
        # Step: Name
        if current_step == "name":
            result = validate_name(user_input)
            if not result.valid:
                return IVRResponse(
                    message=f"❌ {result.error}\n\n¿Cómo quieres llamar a la tarjeta?",
                    next_step="name",
                    data=temp_data,
                )
            
            temp_data["name"] = result.value
            return IVRResponse(
                message=(
                    f"💳 Tarjeta: *{result.value}*\n\n"
                    "¿Qué tipo de tarjeta es?\n\n"
                    "*1.* Crédito 💳\n"
                    "*2.* Débito 🏧"
                ),
                next_step="type",
                data=temp_data,
            )
        
        # Step: Type (credit/debit)
        if current_step == "type":
            card_type = CARD_TYPES.get(text)
            if not card_type:
                return IVRResponse(
                    message=(
                        "❌ No entendí. Selecciona el tipo:\n\n"
                        "*1.* Crédito\n"
                        "*2.* Débito"
                    ),
                    next_step="type",
                    data=temp_data,
                )
            
            temp_data["card_type"] = card_type
            type_display = "Crédito" if card_type == "credit" else "Débito"
            
            return IVRResponse(
                message=(
                    f"💳 {temp_data['name']} ({type_display})\n\n"
                    "¿Cuál es la red de la tarjeta?\n\n"
                    "*1.* Visa\n"
                    "*2.* Mastercard\n"
                    "*3.* American Express\n"
                    "*4.* Otra"
                ),
                next_step="network",
                data=temp_data,
            )
        
        # Step: Network
        if current_step == "network":
            network = CARD_NETWORKS.get(text)
            if not network:
                return IVRResponse(
                    message=(
                        "❌ No entendí. Selecciona la red:\n\n"
                        "*1.* Visa\n"
                        "*2.* Mastercard\n"
                        "*3.* American Express\n"
                        "*4.* Otra"
                    ),
                    next_step="network",
                    data=temp_data,
                )
            
            temp_data["network"] = network
            
            return IVRResponse(
                message=(
                    f"💳 {temp_data['name']} - {network.title()}\n\n"
                    "¿Cuáles son los últimos 4 dígitos de la tarjeta?\n\n"
                    "_Esto ayuda a identificarla. Ejemplo: 4532_"
                ),
                next_step="last_four",
                data=temp_data,
            )
        
        # Step: Last Four Digits
        if current_step == "last_four":
            # Validate: exactly 4 digits
            digits = "".join(c for c in user_input if c.isdigit())
            
            if len(digits) != 4:
                return IVRResponse(
                    message=(
                        "❌ Por favor ingresa exactamente 4 dígitos.\n\n"
                        "¿Cuáles son los últimos 4 dígitos de la tarjeta?"
                    ),
                    next_step="last_four",
                    data=temp_data,
                )
            
            temp_data["last_four"] = digits
            
            return IVRResponse(
                message=(
                    f"💳 *{temp_data['name']}* terminada en {digits}\n\n"
                    "¿De qué color es la tarjeta? _(opcional, para identificarla)_\n\n"
                    "*1.* 🔵 Azul\n"
                    "*2.* ⚫ Negro\n"
                    "*3.* 🟡 Dorado\n"
                    "*4.* ⚪ Plateado\n"
                    "*5.* 🟢 Verde\n"
                    "*6.* 🔴 Rojo\n\n"
                    "_O escribe \"saltar\" para omitir_"
                ),
                next_step="color",
                data=temp_data,
            )
        
        # Step: Color (optional)
        if current_step == "color":
            if text in ("saltar", "skip", "omitir", "0"):
                temp_data["color"] = None
            else:
                color = CARD_COLORS.get(text)
                temp_data["color"] = color  # None if not recognized
            
            return IVRResponse(
                message=self._build_card_confirmation(temp_data),
                next_step="confirm",
                data=temp_data,
            )
        
        # Step: Confirm
        if current_step == "confirm":
            if text in CONFIRM_KEYWORDS:
                try:
                    card = self._create_card_from_data(user, temp_data)
                    
                    return IVRResponse(
                        message=(
                            f"✅ ¡Tarjeta configurada!\n\n"
                            f"💳 *{card.name}*\n"
                            f"• Tipo: {card.card_type.title()}\n"
                            f"• Red: {card.network.title()}\n"
                            f"• Termina en: {card.last_four_digits}\n\n"
                            f"Ahora puedes registrar gastos con esta tarjeta:\n"
                            f"_\"50000 almuerzo con {card.name}\"_"
                        ),
                        flow_complete=True,
                        data={"card_id": str(card.id)},
                    )
                except Exception as e:
                    logger.error("card_creation_failed", error=str(e))
                    return IVRResponse(
                        message=f"❌ Error creando tarjeta: {str(e)}",
                        flow_complete=True,
                    )
            
            elif text in DENY_KEYWORDS:
                return IVRResponse(
                    message=(
                        "❌ Configuración cancelada.\n\n"
                        "Escribe \"nueva tarjeta\" para intentar de nuevo."
                    ),
                    flow_complete=True,
                )
            
            else:
                return IVRResponse(
                    message=(
                        "❓ No entendí.\n\n"
                        "Responde *1* para confirmar o *2* para cancelar."
                    ),
                    next_step="confirm",
                    data=temp_data,
                )
        
        # Default: start over
        return IVRResponse(
            message="💳 Escribe \"nueva tarjeta\" para configurar una tarjeta.",
            flow_complete=True,
        )
    
    def _build_card_confirmation(self, temp_data: dict[str, Any]) -> str:
        """Build confirmation message for card configuration."""
        type_display = "Crédito" if temp_data.get("card_type") == "credit" else "Débito"
        network = temp_data.get("network", "").title()
        color = temp_data.get("color")
        color_display = f"• Color: {color.title()}\n" if color else ""
        
        return (
            f"📋 *Confirma tu tarjeta:*\n\n"
            f"• Nombre: {temp_data.get('name')}\n"
            f"• Tipo: {type_display}\n"
            f"• Red: {network}\n"
            f"• Últimos 4: {temp_data.get('last_four')}\n"
            f"{color_display}\n"
            f"¿Crear esta tarjeta?\n"
            f"*1.* Sí, crear\n"
            f"*2.* No, cancelar"
        )
    
    def _create_card_from_data(self, user: User, temp_data: dict[str, Any]):
        """Create card from accumulated flow data."""
        from app.storage.card_writer import create_card_for_user
        
        result = create_card_for_user(
            db=self.db,
            user_id=user.id,
            name=temp_data["name"],
            card_type=temp_data["card_type"],
            network=temp_data["network"],
            last_four_digits=temp_data["last_four"],
            issuer=None,  # Could be added in a future step
            is_default=False,  # First card will be default, handled by card_writer
        )
        
        if not result.success:
            raise Exception(result.error)
        
        return result.card

