# routers/phase_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from enum import Enum

class LifecyclePhase(str, Enum):
    EMERGING = "Emerging"
    GROWING = "Growing"
    MATURE = "Mature"
    DECLINING = "Declining"

class LifecycleData(BaseModel):
    phase: LifecyclePhase
    current_year_count: int
    previous_year_count: int
    yoy_growth_percent: float
    description: str

router = APIRouter()

@router.get("/phase", response_model=LifecycleData)
async def get_ingredient_phase(
    ingredient: str = Query(..., description="Ingredient name"),
    source: str = Query("recipe", description="Data source: 'recipe' or 'menu'")
):
    try:
        if source not in ["recipe", "menu"]:
            raise HTTPException(status_code=400, detail="Source must be 'recipe' or 'menu'")

        ingredient_pattern = f"'%{ingredient}%'"

        phase_query = f"""
        SELECT
            COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END) AS previous_year_count,
            COUNT(DISTINCT CASE WHEN year = 2024 THEN dish_id END) AS current_year_count,
            CASE
                WHEN COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END) = 0 THEN 0
                ELSE ROUND(
                    (COUNT(DISTINCT CASE WHEN year = 2024 THEN dish_id END) - 
                     COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END)) * 100.0 / 
                    NULLIF(COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END), 0),
                    2
                )
            END AS yoy_growth_percent
        FROM ingredient_details
        WHERE ingredient_name ILIKE {ingredient_pattern} 
        AND source = '{source}' 
        AND year IN (2023, 2024);
        """

        result = await execute_query(
            phase_query,
            options=QueryOptions(cacheable=True, ttl=600000)
        )

        if not result["rows"]:
            return LifecycleData(
                phase=LifecyclePhase.EMERGING,
                current_year_count=0,
                previous_year_count=0,
                yoy_growth_percent=0.0,
                description="No data available for this ingredient"
            )

        row = result["rows"][0]
        previous_year_count = int(row["previous_year_count"] or 0)
        current_year_count = int(row["current_year_count"] or 0)
        yoy_growth_percent = float(row["yoy_growth_percent"] or 0.0)

        # Classify phase
        if previous_year_count == 0 and current_year_count > 0:
            phase = LifecyclePhase.EMERGING
            description = f"New ingredient appearing in {current_year_count} dishes this year"
        elif current_year_count == 0:
            phase = LifecyclePhase.DECLINING
            description = "Ingredient no longer appearing in dishes"
        elif yoy_growth_percent > 20:
            phase = LifecyclePhase.GROWING
            description = f"Strong growth of {yoy_growth_percent:.1f}% year-over-year"
        elif yoy_growth_percent < -20:
            phase = LifecyclePhase.DECLINING
            description = f"Significant decline of {yoy_growth_percent:.1f}% year-over-year"
        else:
            phase = LifecyclePhase.MATURE
            description = f"Stable with {yoy_growth_percent:.1f}% year-over-year change"

        return LifecycleData(
            phase=phase,
            current_year_count=current_year_count,
            previous_year_count=previous_year_count,
            yoy_growth_percent=yoy_growth_percent,
            description=description
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")