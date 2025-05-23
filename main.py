# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from contextlib import asynccontextmanager

# Import routers
from routers import (
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
    trending_router,
    phase_router
)
from database.connection import close_db_connection, get_connection_info, get_db_connection, test_motherduck_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up FlavorLens API...")
    yield
    # Shutdown
    print("Shutting down FlavorLens API...")
    await close_db_connection()

# Make sure this is at module level, not inside any function
app = FastAPI(
    title="FlavorLens API",
    description="API for ingredient analytics and food trend insights",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
    expose_headers=settings.cors_expose_headers,
    max_age=settings.cors_max_age,
)

# Include routers
app.include_router(texture_router.router, prefix="/api", tags=["texture"])
app.include_router(temperature_router.router, prefix="/api", tags=["temperature"])
app.include_router(geographic_router.router, prefix="/api", tags=["geographic"])
app.include_router(format_router.router, prefix="/api", tags=["format"])
app.include_router(applications_router.router, prefix="/api", tags=["applications"])
app.include_router(category_router.router, prefix="/api", tags=["category"])
app.include_router(subcategory_router.router, prefix="/api", tags=["subcategory"])
app.include_router(recipe_share_router.router, prefix="/api", tags=["recipe"])
app.include_router(menu_share_router.router, prefix="/api", tags=["menu"])
app.include_router(lifecycle_router.router, prefix="/api", tags=["lifecycle"])
app.include_router(flavor_profile_router.router, prefix="/api", tags=["flavor"])
app.include_router(cuisine_router.router, prefix="/api", tags=["cuisine"])
app.include_router(category_penetration_router.router, prefix="/api", tags=["penetration"])
app.include_router(trending_router.router, prefix="/api", tags=["trending"])
app.include_router(phase_router.router, prefix="/api") 

@app.get("/")
async def root():
    return {"message": "FlavorLens API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "API is working"}

# Add this to main.py after your other endpoints

from database.connection import get_connection_info, test_motherduck_connection

@app.get("/debug/connection")
async def debug_connection():
    """Get detailed connection information"""
    return await get_connection_info()

@app.get("/debug/test-motherduck")
async def debug_test_motherduck():
    """Test MotherDuck connection with detailed diagnostics"""
    return await test_motherduck_connection()

# This should be at the bottom
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )