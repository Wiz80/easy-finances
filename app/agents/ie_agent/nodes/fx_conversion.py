"""
FX Conversion node for IE Agent.

Performs exchange rate lookup when the expense currency differs from
the user's home currency. Uses end-of-day rates for budget synchronization.
"""

import asyncio

from app.agents.ie_agent.state import IEAgentState
from app.logging_config import get_logger
from app.tools.fx_lookup import FXLookup, FXLookupError

logger = get_logger(__name__)


def lookup_fx_rate_node(state: IEAgentState) -> IEAgentState:
    """
    FX Rate Lookup node: Get exchange rate if currencies differ.

    This node:
    1. Checks if extracted expense currency differs from user's home currency
    2. Fetches EOD exchange rate using FXLookup tool
    3. Stores conversion result in state

    The FX conversion is used for:
    - Displaying expense in home currency to user
    - Budget synchronization (deducting from budget in consistent currency)

    Args:
        state: Current agent state with extracted expense

    Returns:
        Updated state with fx_conversion and amount_in_home_currency

    Note:
        Uses end-of-day (EOD) rates which are cached for 24 hours.
        This ensures budget calculations are consistent throughout the day.
    """
    request_id = state.get("request_id", "unknown")

    logger.debug(
        "lookup_fx_rate_node_start",
        request_id=request_id,
    )

    extracted_expense = state.get("extracted_expense")
    user_home_currency = state.get("user_home_currency")

    # If no extracted expense, skip FX lookup
    if extracted_expense is None:
        logger.debug(
            "lookup_fx_rate_node_skip",
            request_id=request_id,
            reason="no_extracted_expense",
        )
        return state

    # If no home currency set, skip FX lookup
    if not user_home_currency:
        logger.debug(
            "lookup_fx_rate_node_skip",
            request_id=request_id,
            reason="no_home_currency",
        )
        return state

    # Get expense currency
    expense_currency = extracted_expense.currency
    if not expense_currency:
        logger.debug(
            "lookup_fx_rate_node_skip",
            request_id=request_id,
            reason="no_expense_currency",
        )
        return state

    # Normalize currencies for comparison
    expense_currency = expense_currency.upper().strip()
    user_home_currency = user_home_currency.upper().strip()

    # If same currency, no conversion needed
    if expense_currency == user_home_currency:
        logger.debug(
            "lookup_fx_rate_node_skip",
            request_id=request_id,
            reason="same_currency",
            currency=expense_currency,
        )
        return {
            **state,
            "amount_in_home_currency": float(extracted_expense.amount),
        }

    # Perform FX lookup
    try:
        fx_result = asyncio.get_event_loop().run_until_complete(
            _async_fx_lookup(
                from_currency=expense_currency,
                to_currency=user_home_currency,
                amount=extracted_expense.amount,
            )
        )

        logger.info(
            "lookup_fx_rate_node_success",
            request_id=request_id,
            from_currency=expense_currency,
            to_currency=user_home_currency,
            rate=str(fx_result.rate),
            original_amount=str(extracted_expense.amount),
            converted_amount=str(fx_result.converted_amount),
            source=fx_result.source,
        )

        return {
            **state,
            "fx_conversion": fx_result,
            "amount_in_home_currency": (
                float(fx_result.converted_amount)
                if fx_result.converted_amount
                else None
            ),
        }

    except FXLookupError as e:
        logger.warning(
            "lookup_fx_rate_node_error",
            request_id=request_id,
            from_currency=expense_currency,
            to_currency=user_home_currency,
            error=str(e),
        )
        # Don't fail the whole extraction - just log and continue without FX
        errors = state.get("errors", [])
        errors.append(f"FX lookup failed: {str(e)}")
        return {
            **state,
            "errors": errors,
        }

    except Exception as e:
        logger.error(
            "lookup_fx_rate_node_unexpected_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        errors = state.get("errors", [])
        errors.append(f"Unexpected FX error: {str(e)}")
        return {
            **state,
            "errors": errors,
        }


async def _async_fx_lookup(
    from_currency: str,
    to_currency: str,
    amount,
):
    """
    Async wrapper for FX lookup.

    Uses EOD rates for budget consistency.
    """
    from decimal import Decimal

    fx_lookup = FXLookup()

    # Convert amount to Decimal if needed
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    return await fx_lookup.get_rate(
        from_currency=from_currency,
        to_currency=to_currency,
        amount=amount,
        use_eod=True,  # Use end-of-day rate for budget sync
    )


async def lookup_fx_rate_node_async(state: IEAgentState) -> IEAgentState:
    """
    Async version of lookup_fx_rate_node.

    Use this when running in an async context.
    """
    request_id = state.get("request_id", "unknown")

    logger.debug(
        "lookup_fx_rate_node_async_start",
        request_id=request_id,
    )

    extracted_expense = state.get("extracted_expense")
    user_home_currency = state.get("user_home_currency")

    if extracted_expense is None or not user_home_currency:
        return state

    expense_currency = extracted_expense.currency
    if not expense_currency:
        return state

    expense_currency = expense_currency.upper().strip()
    user_home_currency = user_home_currency.upper().strip()

    if expense_currency == user_home_currency:
        return {
            **state,
            "amount_in_home_currency": float(extracted_expense.amount),
        }

    try:
        fx_result = await _async_fx_lookup(
            from_currency=expense_currency,
            to_currency=user_home_currency,
            amount=extracted_expense.amount,
        )

        logger.info(
            "lookup_fx_rate_node_async_success",
            request_id=request_id,
            from_currency=expense_currency,
            to_currency=user_home_currency,
            rate=str(fx_result.rate),
        )

        return {
            **state,
            "fx_conversion": fx_result,
            "amount_in_home_currency": (
                float(fx_result.converted_amount)
                if fx_result.converted_amount
                else None
            ),
        }

    except FXLookupError as e:
        logger.warning(
            "lookup_fx_rate_node_async_error",
            request_id=request_id,
            error=str(e),
        )
        errors = state.get("errors", [])
        errors.append(f"FX lookup failed: {str(e)}")
        return {
            **state,
            "errors": errors,
        }

