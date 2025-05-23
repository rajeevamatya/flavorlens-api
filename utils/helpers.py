# utils/helpers.py
"""Utility functions for FlavorLens API."""

import hashlib
import time
from typing import Any, Dict, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def generate_cache_key(query: str, params: List[Any]) -> str:
    """Generate a cache key from query and parameters."""
    content = f"{query}:{str(params)}"
    return hashlib.md5(content.encode()).hexdigest()

def is_cache_valid(cache_entry: Dict[str, Any], ttl: int) -> bool:
    """Check if cache entry is still valid."""
    current_time = int(time.time() * 1000)
    return (current_time - cache_entry["timestamp"]) < ttl

def format_ingredient_pattern(ingredient: str) -> str:
    """Format ingredient name for SQL ILIKE pattern."""
    return f"'%{ingredient}%'"

def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default fallback."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int_conversion(value: Any, default: int = 0) -> int:
    """Safely convert value to int with default fallback."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def log_query_performance(query: str, execution_time: float, row_count: int):
    """Log query performance metrics."""
    logger.info(
        f"Query executed in {execution_time:.3f}s, returned {row_count} rows. "
        f"Query: {query[:100]}{'...' if len(query) > 100 else ''}"
    )