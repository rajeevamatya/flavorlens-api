# routers/cuisine_analysis_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional

class CuisineData(BaseModel):
    cuisine: str
    percentage: float
    growth: float
    penetration: float
    dish_count: int

class PieChartData(BaseModel):
    name: str
    value: int
    percentage: float
    fill: str

class PenetrationGrowthData(BaseModel):
    name: str
    penetration: float
    growth: float

class CuisineAnalysisResponse(BaseModel):
    ingredient: str
    cuisine_data: List[CuisineData]
    pie_data: List[PieChartData]
    penetration_data: List[PenetrationGrowthData]
    total_dishes: int
    total_cuisines: int
    highest_growth_cuisine: Optional[CuisineData]
    highest_penetration_cuisine: Optional[CuisineData]
    emerging_cuisines: List[CuisineData]
    avg_growth_rate: float

router = APIRouter()

@router.get("/cuisine/analysis", response_model=CuisineAnalysisResponse)
async def get_cuisine_analysis(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Single comprehensive query for all cuisine analysis data
        cuisine_analysis_query = f"""
        WITH overall_cuisine_counts AS (
            -- Overall distribution across all years
            SELECT 
                cuisine,
                COUNT(DISTINCT dish_id) AS total_dish_count,
                AVG(star_rating) as avg_rating
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND cuisine IS NOT NULL
                AND cuisine != ''
            GROUP BY cuisine
        ),
        growth_counts AS (
            -- Growth calculation: 2023 vs 2024
            SELECT 
                cuisine,
                COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END) AS count_2023,
                COUNT(DISTINCT CASE WHEN year = 2024 THEN dish_id END) AS count_2024
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND cuisine IS NOT NULL
                AND cuisine != ''
            GROUP BY cuisine
        ),
        total_ingredient_dishes AS (
            -- Total ingredient dishes across all cuisines for percentage calculation
            SELECT COUNT(DISTINCT dish_id) AS total_count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND cuisine IS NOT NULL
                AND cuisine != ''
        ),
        cuisine_totals AS (
            -- Total dishes per cuisine (all ingredients) for penetration calculation
            SELECT 
                cuisine,
                COUNT(DISTINCT dish_id) as total_cuisine_dishes
            FROM ingredient_details
            WHERE cuisine IS NOT NULL
                AND cuisine != ''
            GROUP BY cuisine
        )
        SELECT 
            occ.cuisine,
            occ.total_dish_count as dish_count,
            ROUND(occ.total_dish_count * 100.0 / NULLIF(tid.total_count, 0), 1) as percentage,
            CASE 
                WHEN gc.count_2023 = 0 OR gc.count_2023 IS NULL THEN 
                    CASE 
                        WHEN gc.count_2024 > 0 THEN 100.0
                        ELSE 0.0
                    END
                ELSE ROUND((gc.count_2024 - gc.count_2023) * 100.0 / NULLIF(gc.count_2023, 0), 1)
            END as growth_rate,
            ROUND(occ.total_dish_count * 100.0 / NULLIF(ct.total_cuisine_dishes, 0), 1) as penetration_rate,
            occ.avg_rating,
            COALESCE(gc.count_2024, 0) as count_2024,
            COALESCE(gc.count_2023, 0) as count_2023
        FROM overall_cuisine_counts occ
        LEFT JOIN growth_counts gc ON occ.cuisine = gc.cuisine
        LEFT JOIN cuisine_totals ct ON occ.cuisine = ct.cuisine
        CROSS JOIN total_ingredient_dishes tid
        WHERE occ.total_dish_count >= 2  -- Filter out cuisines with very few dishes
        ORDER BY occ.total_dish_count DESC
        LIMIT 12;
        """
        
        result = await execute_query(
            cuisine_analysis_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if not result["rows"]:
            raise HTTPException(status_code=404, detail=f"No cuisine data found for ingredient: {ingredient}")
        
        # Process the data
        cuisine_data = []
        total_dishes = 0
        colors = ['#00255a', '#199ef3', '#3179c0', '#5590d6', '#84abdd', '#adc5e5', '#c3d5ec', '#d1e3f6']
        
        for row in result["rows"]:
            try:
                cuisine = CuisineData(
                    cuisine=str(row["cuisine"]),
                    percentage=float(row["percentage"]) if row["percentage"] is not None else 0.0,
                    growth=float(row["growth_rate"]) if row["growth_rate"] is not None else 0.0,
                    penetration=float(row["penetration_rate"]) if row["penetration_rate"] is not None else 0.0,
                    dish_count=int(row["dish_count"])
                )
                cuisine_data.append(cuisine)
                total_dishes += cuisine.dish_count
                
            except Exception as e:
                print(f"Error processing cuisine row {row}: {e}")
                continue
        
        if not cuisine_data:
            raise HTTPException(status_code=404, detail=f"No valid cuisine data found for ingredient: {ingredient}")
        
        # Create pie chart data
        pie_data = []
        for i, cuisine in enumerate(cuisine_data[:8]):  # Top 8 for pie chart
            pie_data.append(PieChartData(
                name=cuisine.cuisine,
                value=cuisine.dish_count,
                percentage=cuisine.percentage,
                fill=colors[i % len(colors)]
            ))
        
        # Create penetration/growth data (sorted by penetration for chart)
        penetration_data = []
        sorted_cuisines = sorted(cuisine_data[:8], key=lambda x: x.penetration, reverse=True)
        for cuisine in sorted_cuisines:
            penetration_data.append(PenetrationGrowthData(
                name=cuisine.cuisine,
                penetration=cuisine.penetration,
                growth=cuisine.growth
            ))
        
        # Calculate insights
        highest_growth = max(cuisine_data, key=lambda x: x.growth) if cuisine_data else None
        highest_penetration = max(cuisine_data, key=lambda x: x.penetration) if cuisine_data else None
        
        # Find emerging cuisines (high growth > 20%, moderate penetration < 50%)
        emerging_cuisines = [
            c for c in cuisine_data 
            if c.growth > 20.0 and c.penetration < 50.0
        ]
        emerging_cuisines.sort(key=lambda x: x.growth, reverse=True)
        
        # Calculate average growth rate
        avg_growth = sum(c.growth for c in cuisine_data) / len(cuisine_data) if cuisine_data else 0.0
        
        return CuisineAnalysisResponse(
            ingredient=ingredient.title(),
            cuisine_data=cuisine_data,
            pie_data=pie_data,
            penetration_data=penetration_data,
            total_dishes=total_dishes,
            total_cuisines=len(cuisine_data),
            highest_growth_cuisine=highest_growth,
            highest_penetration_cuisine=highest_penetration,
            emerging_cuisines=emerging_cuisines[:5],  # Top 5 emerging
            avg_growth_rate=round(avg_growth, 1)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cuisine analysis data")