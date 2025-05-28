# routers/summary_stats_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class MetricBox(BaseModel):
    title: str
    value: str
    growth: Optional[str] = None
    is_positive: Optional[bool] = None
    phase: Optional[int] = None
    total_phases: Optional[int] = None
    description: str

class SummaryStatsResponse(BaseModel):
    ingredient: str
    metrics: List[MetricBox]

class LifecyclePhase(str, Enum):
    EMERGING = "Emerging"
    GROWING = "Growing"
    MATURE = "Mature"
    DECLINING = "Declining"

router = APIRouter()

def determine_lifecycle_phase(current_count: int, previous_count: int, yoy_growth: float) -> tuple[LifecyclePhase, int]:
    """Determine lifecycle phase and phase number"""
    if previous_count == 0 and current_count > 0:
        return LifecyclePhase.EMERGING, 1
    elif current_count == 0:
        return LifecyclePhase.DECLINING, 4
    elif yoy_growth > 20:
        return LifecyclePhase.GROWING, 2
    elif yoy_growth < -20:
        return LifecyclePhase.DECLINING, 4
    else:
        return LifecyclePhase.MATURE, 3

@router.get("/general/summary-stats", response_model=SummaryStatsResponse)
async def get_summary_stats(ingredient: str = Query(..., description="Ingredient name")):
    """Get all summary statistics for an ingredient in one call"""
    try:
        ingredient_pattern = f"'%{ingredient}%'"

        # Combined query to get all data at once
        summary_query = f"""
        WITH yearly_totals AS (
            SELECT 
                year,
                source,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE year IN (2023, 2024)
            GROUP BY year, source
        ),
        ingredient_data AS (
            SELECT 
                year,
                source,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND year IN (2023, 2024)
            GROUP BY year, source
        )
        SELECT 
            yt.year,
            yt.source,
            COALESCE(id.ingredient_dishes, 0) AS ingredient_dishes,
            yt.total_dishes,
            ROUND(
                COALESCE(id.ingredient_dishes, 0) * 100.0 / NULLIF(yt.total_dishes, 0), 
                2
            ) AS share_percent
        FROM yearly_totals yt
        LEFT JOIN ingredient_data id ON yt.year = id.year AND yt.source = id.source
        ORDER BY yt.year, yt.source;
        """

        result = await execute_query(
            summary_query,
            options=QueryOptions(cacheable=True, ttl=600000)
        )

        if not result["rows"]:
            # Return default values if no data
            metrics = [
                MetricBox(title="Recipe Share", value="0.0%", growth="+0.0%", is_positive=True, description="Share of recipes containing this ingredient"),
                MetricBox(title="Menu Share", value="0.0%", growth="+0.0%", is_positive=True, description="Presence on restaurant menus"),
                MetricBox(title="Social Content Share", value="0.0%", growth="+0.0%", is_positive=True, description="Share of social content mentions"),
                MetricBox(title="Adoption Phase", value="Emerging", phase=1, total_phases=4, description="Current lifecycle position")
            ]
            return SummaryStatsResponse(ingredient=ingredient, metrics=metrics)

        # Process the results
        data_by_source_year = {}
        for row in result["rows"]:
            key = f"{row['source']}_{row['year']}"
            data_by_source_year[key] = {
                'share_percent': float(row['share_percent'] or 0),
                'ingredient_dishes': int(row['ingredient_dishes'] or 0)
            }

        # Calculate metrics
        recipe_2024 = data_by_source_year.get('recipe_2024', {'share_percent': 0, 'ingredient_dishes': 0})
        recipe_2023 = data_by_source_year.get('recipe_2023', {'share_percent': 0, 'ingredient_dishes': 0})
        menu_2024 = data_by_source_year.get('menu_2024', {'share_percent': 0, 'ingredient_dishes': 0})
        menu_2023 = data_by_source_year.get('menu_2023', {'share_percent': 0, 'ingredient_dishes': 0})
        social_2024 = data_by_source_year.get('social_2024', {'share_percent': 0, 'ingredient_dishes': 0})
        social_2023 = data_by_source_year.get('social_2023', {'share_percent': 0, 'ingredient_dishes': 0})

        # Calculate growth rates
        recipe_growth = recipe_2024['share_percent'] - recipe_2023['share_percent']
        menu_growth = menu_2024['share_percent'] - menu_2023['share_percent']
        social_growth = social_2024['share_percent'] - social_2023['share_percent']

        # Calculate overall YoY growth for lifecycle phase
        total_2024 = recipe_2024['ingredient_dishes'] + menu_2024['ingredient_dishes'] + social_2024['ingredient_dishes']
        total_2023 = recipe_2023['ingredient_dishes'] + menu_2023['ingredient_dishes'] + social_2023['ingredient_dishes']
        
        if total_2023 > 0:
            yoy_growth = ((total_2024 - total_2023) / total_2023) * 100
        else:
            yoy_growth = 100 if total_2024 > 0 else 0

        # Determine lifecycle phase
        lifecycle_phase, phase_number = determine_lifecycle_phase(total_2024, total_2023, yoy_growth)

        # Build metrics response (removed Innovation Potential)
        metrics = [
            MetricBox(
                title="Recipe Share",
                value=f"{recipe_2024['share_percent']:.1f}%",
                growth=f"{recipe_growth:+.1f}%",
                is_positive=recipe_growth >= 0,
                description="Share of recipes containing this ingredient"
            ),
            MetricBox(
                title="Menu Share",
                value=f"{menu_2024['share_percent']:.1f}%",
                growth=f"{menu_growth:+.1f}%",
                is_positive=menu_growth >= 0,
                description="Presence on restaurant menus"
            ),
            MetricBox(
                title="Social Content Share",
                value=f"{social_2024['share_percent']:.1f}%",
                growth=f"{social_growth:+.1f}%",
                is_positive=social_growth >= 0,
                description="Share of social content mentions"
            ),
            MetricBox(
                title="Adoption Phase",
                value=lifecycle_phase.value,
                phase=phase_number,
                total_phases=4,
                description="Current lifecycle position"
            )
        ]

        return SummaryStatsResponse(ingredient=ingredient, metrics=metrics)

    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch summary statistics")