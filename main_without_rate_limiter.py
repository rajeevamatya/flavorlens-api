# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from contextlib import asynccontextmanager

# Import routers directly

from routers.summary_stats_router import router as summary_stats_router
from routers.general_trends_router import router as general_trends_router
from routers.season_router import router as season_router

from routers.category_analysis_router import router as category_analysis_router
from routers.category_trends_router import router as category_trends_router
from routers.cuisine_analysis_router import router as cuisine_analysis_router
from routers.subcategory_analysis_router import router as subcategory_analysis_router
from routers.dish_router import router as dish_router

from routers.applications_router import router as applications_router
from routers.pairings_router import router as pairings_router

from routers.consumer_insights_attributes_router import router as consumer_insights_attributes_router
# from routers.consumer_insights_flavor_router import router as consumer_insights_flavor_router




from database.connection import close_db_connection, get_db_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - pre-warm database connection
    print("Starting up FlavorLens API...")
    await get_db_connection()  # Establish connection at startup
    yield
    # Shutdown
    print("Shutting down FlavorLens API...")
    await close_db_connection()

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
# app.include_router(temperature_router, prefix="/api", tags=["temperature"])
# app.include_router(geographic_router, prefix="/api", tags=["geographic"])
# app.include_router(format_router, prefix="/api", tags=["format"])

app.include_router(summary_stats_router, prefix="/api", tags=["summary-stats"])
app.include_router(general_trends_router, prefix="/api", tags=["general-trends"])
app.include_router(season_router, prefix="/api", tags=["season"])

app.include_router(category_analysis_router, prefix="/api", tags=["category-analysis"])
app.include_router(category_trends_router, prefix="/api", tags=["category-trends"])
app.include_router(cuisine_analysis_router, prefix="/api", tags=["cuisine-analysis"])
app.include_router(subcategory_analysis_router, prefix="/api", tags=["subcategory-distribution"])
app.include_router(dish_router, prefix="/api", tags=["dish"])

app.include_router(applications_router, prefix="/api", tags=["applications"])
app.include_router(pairings_router, prefix="/api", tags=["pairings"])
app.include_router(consumer_insights_attributes_router, prefix="/api", tags=["consumer-insights-attributes"])
# app.include_router(consumer_insights_flavor_router, prefix="/api", tags=["consumer-insights-flavor"])





@app.get("/")
async def root():
    return {"message": "FlavorLens API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "API is working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )