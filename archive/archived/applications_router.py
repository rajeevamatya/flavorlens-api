# routers/applications_router.py
import asyncio
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from typing import List, Optional
from pydantic import BaseModel

class Application(BaseModel):
    category: str
    application: str
    appealScore: float
    penetration: float
    growth: float
    ratings: float
    trend: str

router = APIRouter()

@router.get("/applications", response_model=List[Application])
async def get_applications(
    ingredient: str = Query(..., description="Ingredient name"),
    category: Optional[str] = Query(None, description="Category filter")
):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        category_filter = ""
        if category and category != 'all':
            category_filter = f"AND general_category ILIKE '{category.capitalize()}%'"
        
        applications_query = f"""
        WITH ingredient_applications AS (
            SELECT 
                general_category AS category,
                specific_category AS application,
                star_rating,
                num_ratings,
                COUNT(*) OVER (PARTITION BY general_category, specific_category) AS application_count,
                COUNT(*) OVER (PARTITION BY general_category) AS category_count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
                AND specific_category IS NOT NULL
                {category_filter}
        ),
        year_counts AS (
            SELECT 
                general_category,
                specific_category,
                COUNT(CASE WHEN EXTRACT(YEAR FROM dish_date_created) = EXTRACT(YEAR FROM CURRENT_DATE) THEN 1 END) AS current_year,
                COUNT(CASE WHEN EXTRACT(YEAR FROM dish_date_created) = EXTRACT(YEAR FROM CURRENT_DATE) - 1 THEN 1 END) AS previous_year
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
                AND specific_category IS NOT NULL
                {category_filter}
            GROUP BY
                general_category, specific_category
        ),
        application_metrics AS (
            SELECT 
                ia.category,
                ia.application,
                AVG(ia.star_rating) AS avg_rating,
                SUM(ia.num_ratings) AS total_ratings,
                COUNT(*) AS dish_count,
                MAX(ia.application_count) AS application_count,
                MAX(ia.category_count) AS category_count,
                ROUND(MAX(ia.application_count) * 100.0 / NULLIF(MAX(ia.category_count), 0), 1) AS penetration
            FROM 
                ingredient_applications ia
            GROUP BY
                ia.category, ia.application
        )
        SELECT 
            am.category,
            am.application,
            am.avg_rating,
            am.total_ratings,
            am.dish_count,
            am.penetration,
            COALESCE(yc.current_year, 0) AS current_year_count,
            COALESCE(yc.previous_year, 0) AS previous_year_count,
            CASE
                WHEN COALESCE(yc.previous_year, 0) = 0 AND COALESCE(yc.current_year, 0) > 0 THEN 100.0
                WHEN COALESCE(yc.previous_year, 0) = 0 THEN 0.0
                ELSE ROUND((COALESCE(yc.current_year, 0) - COALESCE(yc.previous_year, 0)) * 100.0 / 
                          NULLIF(COALESCE(yc.previous_year, 0), 0), 1)
            END AS growth,
            ROUND((
                (COALESCE(am.penetration, 0) * 0.7) + 
                (COALESCE(am.avg_rating * 10, 0) * 0.3)
            ), 1) AS appeal_score,
            CASE
                WHEN COALESCE(am.penetration, 0) < 5 AND COALESCE(yc.current_year, 0) > COALESCE(yc.previous_year, 0) * 2 THEN 'Emerging'
                WHEN COALESCE(am.penetration, 0) < 15 AND COALESCE(yc.current_year, 0) > COALESCE(yc.previous_year, 0) * 1.5 THEN 'Trending'
                WHEN COALESCE(am.penetration, 0) > 30 THEN 'Established'
                WHEN COALESCE(am.penetration, 0) > 15 THEN 'Growing'
                ELSE 'Emerging'
            END AS trend
        FROM 
            application_metrics am
        LEFT JOIN
            year_counts yc ON am.category = yc.general_category AND am.application = yc.specific_category
        ORDER BY 
            am.category ASC, appeal_score DESC
        """
        
        result = await execute_query(
            applications_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        applications = []
        if result["rows"]:
            for row in result["rows"]:
                applications.append(Application(
                    category=str(row["category"]) if row["category"] is not None else "Unknown",
                    application=str(row["application"]) if row["application"] is not None else "Unknown",
                    appealScore=float(row["appeal_score"]) if row["appeal_score"] is not None else 0.0,
                    penetration=float(row["penetration"]) if row["penetration"] is not None else 0.0,
                    growth=float(row["growth"]) if row["growth"] is not None else 0.0,
                    ratings=float(row["avg_rating"]) if row["avg_rating"] is not None else 0.0,
                    trend=str(row["trend"]) if row["trend"] is not None else "Unknown"
                ))
        
        # Sort by appeal score
        applications.sort(key=lambda x: x.appealScore, reverse=True)
        return applications
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch applications data")