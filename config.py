# config.py
"""Configuration settings for FlavorLens API."""

from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

CURRENT_YEAR = 2024

class Settings(BaseSettings):
    """Application settings."""
    
    # Database settings
    motherduck_token: Optional[str] = None
    database_url: str = "md:flavorlens"
    
    # API settings
    api_title: str = "FlavorLens API"
    api_description: str = "API for ingredient analytics and food trend insights"
    api_version: str = "1.0.0"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    
    # Cache settings
    default_cache_ttl: int = 3600000  # 1 hour in milliseconds
    enable_caching: bool = True
    
    # CORS settings - Updated for proper cross-origin communication
    # CORS settings - Updated for proper cross-origin communication
    cors_origins: List[str] = [
        "http://localhost:3000",      # Next.js development server
        "http://localhost:8000",      # FastAPI running locally
        "http://127.0.0.1:3000",      # Alternative localhost address
        "http://127.0.0.1:8000",      # Alternative localhost address
        "https://flavorlens.vercel.app",     # Remove trailing slash
        "https://www.flavorlens.vercel.app", # Remove trailing slash
        "https://*.vercel.app",              # Add wildcard for preview deployments
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    cors_allow_headers: List[str] = [
        "Content-Type", 
        "Authorization", 
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers"
    ]
    cors_expose_headers: List[str] = []
    cors_max_age: int = 600  # 10 minutes in seconds
    
    # Updated Config syntax for Pydantic v2
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

# Create global settings instance
settings = Settings()