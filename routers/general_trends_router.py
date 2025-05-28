# routers/general_router.py (cleaned up version)
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class TrendDataPoint(BaseModel):
    year: int
    adoption_percentage: float
    total_dishes: int
    ingredient_dishes: int

class TrendAnalysis(BaseModel):
    current_trend: str  # "increasing", "decreasing", "stable"
    trend_strength: str  # "strong", "moderate", "weak"
    peak_year: Optional[int]
    peak_percentage: Optional[float]
    recent_change: float  # percentage point change from previous year
    average_growth_rate: float  # average annual growth rate
    volatility: str  # "high", "medium", "low"

class TrendData(BaseModel):
    ingredient: str
    data_points: List[TrendDataPoint]
    analysis: TrendAnalysis
    summary: str

# class LifecyclePhase(str, Enum):
#     EMERGING = "Emerging"
#     GROWING = "Growing"
#     MATURE = "Mature"
#     DECLINING = "Declining"

# class LifecycleData(BaseModel):
#     phase: LifecyclePhase
#     current_year_count: int
#     previous_year_count: int
#     yoy_growth_percent: float
#     description: str

router = APIRouter()

def analyze_trend(data_points: List[TrendDataPoint]) -> TrendAnalysis:
    """Analyze trend data to provide insights"""
    if len(data_points) < 2:
        return TrendAnalysis(
            current_trend="insufficient_data",
            trend_strength="unknown",
            peak_year=None,
            peak_percentage=None,
            recent_change=0.0,
            average_growth_rate=0.0,
            volatility="unknown"
        )
    
    # Calculate recent change (last year vs previous year)
    recent_change = data_points[-1].adoption_percentage - data_points[-2].adoption_percentage
    
    # Find peak
    peak_point = max(data_points, key=lambda x: x.adoption_percentage)
    
    # Calculate average growth rate
    years_span = data_points[-1].year - data_points[0].year
    if years_span > 0 and data_points[0].adoption_percentage > 0:
        total_growth = data_points[-1].adoption_percentage / data_points[0].adoption_percentage
        average_growth_rate = (total_growth ** (1/years_span) - 1) * 100
    else:
        average_growth_rate = 0.0
    
    # Determine trend direction
    if recent_change > 0.5:
        current_trend = "increasing"
    elif recent_change < -0.5:
        current_trend = "decreasing"
    else:
        current_trend = "stable"
    
    # Determine trend strength
    if abs(recent_change) > 2.0:
        trend_strength = "strong"
    elif abs(recent_change) > 0.8:
        trend_strength = "moderate"
    else:
        trend_strength = "weak"
    
    # Calculate volatility based on standard deviation
    percentages = [dp.adoption_percentage for dp in data_points]
    if len(percentages) > 1:
        mean_percentage = sum(percentages) / len(percentages)
        variance = sum((x - mean_percentage) ** 2 for x in percentages) / len(percentages)
        std_dev = variance ** 0.5
        
        if std_dev > 1.5:
            volatility = "high"
        elif std_dev > 0.5:
            volatility = "medium"
        else:
            volatility = "low"
    else:
        volatility = "low"
    
    return TrendAnalysis(
        current_trend=current_trend,
        trend_strength=trend_strength,
        peak_year=peak_point.year,
        peak_percentage=peak_point.adoption_percentage,
        recent_change=round(recent_change, 2),
        average_growth_rate=round(average_growth_rate, 2),
        volatility=volatility
    )

def generate_trend_summary(ingredient: str, analysis: TrendAnalysis, data_points: List[TrendDataPoint]) -> str:
    """Generate a human-readable summary of the trend"""
    if not data_points:
        return f"No trend data available for {ingredient}."
    
    current_percentage = data_points[-1].adoption_percentage
    
    if analysis.current_trend == "increasing":
        trend_desc = f"trending upward with {analysis.trend_strength} momentum"
    elif analysis.current_trend == "decreasing":
        trend_desc = f"trending downward with {analysis.trend_strength} decline"
    else:
        trend_desc = "showing stable adoption"
    
    peak_info = ""
    if analysis.peak_year and analysis.peak_percentage:
        if analysis.peak_year == data_points[-1].year:
            peak_info = " and is currently at its peak"
        else:
            peak_info = f", with its peak of {analysis.peak_percentage:.1f}% in {analysis.peak_year}"
    
    return f"{ingredient.title()} is currently at {current_percentage:.1f}% adoption, {trend_desc}{peak_info}."

@router.get("/general/trends", response_model=TrendData)
async def get_trend(ingredient: str = Query(..., description="Ingredient name")):
    """Get trend data with analysis for visualization"""
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        trend_query = f"""
        WITH yearly_totals AS (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE year >= 2018
            GROUP BY year
        ),
        yearly_ingredient AS (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND year >= 2018
            GROUP BY year
        )
        SELECT 
            yt.year,
            yt.total_dishes,
            COALESCE(yi.ingredient_dishes, 0) AS ingredient_dishes,
            ROUND(
                COALESCE(yi.ingredient_dishes, 0) * 100.0 / NULLIF(yt.total_dishes, 0), 
                2
            ) AS adoption_percentage
        FROM yearly_totals yt
        LEFT JOIN yearly_ingredient yi ON yt.year = yi.year
        ORDER BY yt.year;
        """

        result = await execute_query(
            trend_query,
            options=QueryOptions(cacheable=True, ttl=600000)
        )

        if not result["rows"]:
            return TrendData(
                ingredient=ingredient,
                data_points=[],
                analysis=TrendAnalysis(
                    current_trend="no_data",
                    trend_strength="unknown",
                    peak_year=None,
                    peak_percentage=None,
                    recent_change=0.0,
                    average_growth_rate=0.0,
                    volatility="unknown"
                ),
                summary=f"No trend data available for {ingredient}."
            )

        # Process data points
        data_points = []
        for row in result["rows"]:
            data_point = TrendDataPoint(
                year=int(row["year"]),
                adoption_percentage=float(row["adoption_percentage"] or 0.0),
                total_dishes=int(row["total_dishes"] or 0),
                ingredient_dishes=int(row["ingredient_dishes"] or 0)
            )
            data_points.append(data_point)

        # Analyze the trend
        analysis = analyze_trend(data_points)
        
        # Generate summary
        summary = generate_trend_summary(ingredient, analysis, data_points)

        return TrendData(
            ingredient=ingredient,
            data_points=data_points,
            analysis=analysis,
            summary=summary
        )

    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trend data")

# @router.get("/general/lifecycle-phase", response_model=LifecycleData)
# async def get_lifecycle_phase(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"

#         phase_query = f"""
#         SELECT
#             COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END) AS previous_year_count,
#             COUNT(DISTINCT CASE WHEN year = 2024 THEN dish_id END) AS current_year_count,
#             CASE
#                 WHEN COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END) = 0 THEN 0
#                 ELSE ROUND(
#                     (COUNT(DISTINCT CASE WHEN year = 2024 THEN dish_id END) - 
#                      COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END)) * 100.0 / 
#                     NULLIF(COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END), 0),
#                     2
#                 )
#             END AS yoy_growth_percent
#         FROM ingredient_details
#         WHERE ingredient_name ILIKE {ingredient_pattern} 
#         AND year IN (2023, 2024);
#         """

#         result = await execute_query(
#             phase_query,
#             options=QueryOptions(cacheable=True, ttl=600000)
#         )

#         if not result["rows"]:
#             return LifecycleData(
#                 phase=LifecyclePhase.EMERGING,
#                 current_year_count=0,
#                 previous_year_count=0,
#                 yoy_growth_percent=0.0,
#                 description="No data available for this ingredient"
#             )

#         row = result["rows"][0]
#         previous_year_count = int(row["previous_year_count"] or 0)
#         current_year_count = int(row["current_year_count"] or 0)
#         yoy_growth_percent = float(row["yoy_growth_percent"] or 0.0)

#         # Classify phase
#         if previous_year_count == 0 and current_year_count > 0:
#             phase = LifecyclePhase.EMERGING
#             description = f"New ingredient appearing in {current_year_count} dishes this year"
#         elif current_year_count == 0:
#             phase = LifecyclePhase.DECLINING
#             description = "Ingredient no longer appearing in dishes"
#         elif yoy_growth_percent > 20:
#             phase = LifecyclePhase.GROWING
#             description = f"Strong growth of {yoy_growth_percent:.1f}% year-over-year"
#         elif yoy_growth_percent < -20:
#             phase = LifecyclePhase.DECLINING
#             description = f"Significant decline of {yoy_growth_percent:.1f}% year-over-year"
#         else:
#             phase = LifecyclePhase.MATURE
#             description = f"Stable with {yoy_growth_percent:.1f}% year-over-year change"

#         return LifecycleData(
#             phase=phase,
#             current_year_count=current_year_count,
#             previous_year_count=previous_year_count,
#             yoy_growth_percent=yoy_growth_percent,
#             description=description
#         )

#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"Database query error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch lifecycle phase data")