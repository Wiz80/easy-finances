"""Category mapping utilities for expense classification."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models.category import Category

logger = get_logger(__name__)


def get_category_by_slug(session: Session, slug: str) -> Category | None:
    """
    Get category by slug.
    
    Args:
        session: Database session
        slug: Category slug (e.g., 'in_house_food', 'transport')
        
    Returns:
        Category object or None if not found
    """
    try:
        category = session.query(Category).filter(
            Category.slug == slug.lower(),
            Category.is_active == True
        ).first()
        
        if category:
            logger.debug("category_found", slug=slug, category_id=str(category.id))
        else:
            logger.warning("category_not_found", slug=slug)
            
        return category
    except Exception as e:
        logger.error("category_lookup_failed", slug=slug, error=str(e), exc_info=True)
        return None


def get_default_category(session: Session) -> Category:
    """
    Get the default 'misc' category.
    
    Args:
        session: Database session
        
    Returns:
        Category object for 'misc'
        
    Raises:
        ValueError: If 'misc' category doesn't exist
    """
    category = get_category_by_slug(session, "misc")
    
    if not category:
        logger.error("default_category_missing", slug="misc")
        raise ValueError("Default 'misc' category not found in database")
        
    return category


def map_category_candidate(session: Session, category_candidate: str) -> UUID:
    """
    Map a category candidate string to a category UUID.
    Falls back to 'misc' if the candidate is not found.
    
    Args:
        session: Database session
        category_candidate: Suggested category slug
        
    Returns:
        UUID of the matched or default category
    """
    logger.debug("mapping_category", candidate=category_candidate)
    
    # Try to find the suggested category
    category = get_category_by_slug(session, category_candidate)
    
    # Fall back to misc if not found
    if not category:
        logger.info(
            "category_fallback_to_misc", 
            original_candidate=category_candidate
        )
        category = get_default_category(session)
    
    logger.debug("category_mapped", slug=category.slug, category_id=str(category.id))
    return category.id
