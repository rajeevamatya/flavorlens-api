# routers/phase_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from typing import List, Optional, Dict, Any
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
    yoy_growth_percent: Optional[float]
    description: str

router = APIRouter()

@router.get("/phase", response_model=LifecycleData)
async def get_ingredient_phase(
    ingredient: str = Query(..., description="Ingredient name"),
    source: str = Query("recipe", description="Data source: 'recipe' or 'menu'")
):
    try:
        # Safely escape the ingredient parameter
        ingredient_escaped = ingredient.replace("'", "''")  # Escape single quotes
        ingredient_pattern = f"'%{ingredient_escaped}%'"
        
        # Validate source parameter
        if source not in ["recipe", "menu"]:
            raise HTTPException(status_code=400, detail="Source must be 'recipe' or 'menu'")

        phase_query = f"""
        SELECT
            SUM(CASE WHEN year = 2023 THEN ingredient_dish_count END) AS previous_year_count,
            SUM(CASE WHEN year = 2024 THEN ingredient_dish_count END) AS current_year_count,
            CASE
                WHEN SUM(CASE WHEN year = 2023 THEN ingredient_dish_count END) = 0 THEN NULL
                ELSE ROUND(
                    (SUM(CASE WHEN year = 2024 THEN ingredient_dish_count END) - 
                     SUM(CASE WHEN year = 2023 THEN ingredient_dish_count END)) * 100.0 / 
                    SUM(CASE WHEN year = 2023 THEN ingredient_dish_count END),
                    2
                )
            END AS yoy_growth_percent
        FROM (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) FILTER (
                    WHERE ingredient_name ILIKE {ingredient_pattern} AND source = '{source}'
                ) AS ingredient_dish_count
            FROM flavorlens.main.ingredient_details
            WHERE year IN (2023, 2024)
            GROUP BY year
        ) counts;
        """

        result = await execute_query(
            phase_query,
            options=QueryOptions(cacheable=True, ttl=600000)  # 10 minutes
        )

        if not result["rows"]:
            return LifecycleData(
                phase=LifecyclePhase.EMERGING,
                current_year_count=0,
                previous_year_count=0,
                yoy_growth_percent=None,
                description="No data available for this ingredient"
            )

        row = result["rows"][0]
        previous_year_count = int(row["previous_year_count"]) if row["previous_year_count"] else 0
        current_year_count = int(row["current_year_count"]) if row["current_year_count"] else 0
        yoy_growth_percent = float(row["yoy_growth_percent"]) if row["yoy_growth_percent"] is not None else None

        # Apply trend classification logic
        phase, description = classify_lifecycle_phase(
            previous_year_count, 
            current_year_count, 
            yoy_growth_percent
        )

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


def classify_lifecycle_phase(
    previous_year_count: int, 
    current_year_count: int, 
    yoy_growth_percent: Optional[float]
) -> tuple[LifecyclePhase, str]:
    """
    Classify ingredient lifecycle phase based on trend classification logic:
    - Emerging: Previous year (2023) = 0, Current year (2024) > 0
    - Growing: YoY growth > 20%
    - Mature: YoY growth between -20% and +20% (stable)
    - Declining: YoY growth < -20%
    """
    
    # Emerging: Previous year = 0, Current year > 0
    if previous_year_count == 0 and current_year_count > 0:
        return LifecyclePhase.EMERGING, f"New ingredient appearing in {current_year_count} dishes this year"
    
    # No growth data available (both years are 0 or current year is 0)
    if yoy_growth_percent is None:
        if previous_year_count == 0 and current_year_count == 0:
            return LifecyclePhase.EMERGING, "Ingredient not yet present in dataset"
        elif current_year_count == 0:
            return LifecyclePhase.DECLINING, "Ingredient no longer appearing in dishes"
    
    # Apply growth-based classification
    if yoy_growth_percent is not None:
        if yoy_growth_percent > 20:
            return LifecyclePhase.GROWING, f"Strong growth of {yoy_growth_percent:.1f}% year-over-year"
        elif yoy_growth_percent < -20:
            return LifecyclePhase.DECLINING, f"Significant decline of {yoy_growth_percent:.1f}% year-over-year"
        else:
            return LifecyclePhase.MATURE, f"Stable with {yoy_growth_percent:.1f}% year-over-year change"
    
    # Default case
    return LifecyclePhase.MATURE, "Stable ingredient with consistent presence"