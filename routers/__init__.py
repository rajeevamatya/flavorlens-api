# routers/__init__.py
"""Routers package for FlavorLens API endpoints."""

from . import (
    texture_router,
    temperature_router,
    geographic_router,
    format_router,
    applications_router,
    category_router,
    subcategory_router,
    recipe_share_router,
    menu_share_router,
    lifecycle_router,
    flavor_profile_router,
    cuisine_router,
    category_penetration_router,
    trending_router
)

__all__ = [
    "texture_router",
    "temperature_router", 
    "geographic_router",
    "format_router",
    "applications_router",
    "category_router",
    "subcategory_router",
    "recipe_share_router",
    "menu_share_router",
    "lifecycle_router",
    "flavor_profile_router",
    "cuisine_router",
    "category_penetration_router",
    "trending_router"
]
