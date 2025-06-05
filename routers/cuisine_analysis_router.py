# routers/cuisine_analysis_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
from config import CURRENT_YEAR  # Import CURRENT_YEAR from config

class CuisineData(BaseModel):
    cuisine: str
    percentage: float
    growth: float
    penetration: float
    dish_count: int

class DistributionData(BaseModel):
    name: str
    percentage: float
    dish_count: int

class PenetrationData(BaseModel):
    name: str
    penetration: float
    previous_penetration: float
    growth: float
    dish_count: int

class CuisineAnalysisResponse(BaseModel):
    ingredient: str
    distribution_data: List[DistributionData]  # Top 8 + Others for pie chart
    penetration_data: List[PenetrationData]   # Top 8 for bar chart
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
        previous_year = CURRENT_YEAR - 1
        
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
            -- Growth calculation: previous year vs current year
            SELECT 
                cuisine,
                COUNT(DISTINCT CASE WHEN year = {previous_year} THEN dish_id END) AS count_previous,
                COUNT(DISTINCT CASE WHEN year = {CURRENT_YEAR} THEN dish_id END) AS count_current
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
        ),
        cuisine_totals_by_year AS (
            -- Total dishes per cuisine by year for year-over-year penetration
            SELECT 
                cuisine,
                COUNT(DISTINCT CASE WHEN year = {previous_year} THEN dish_id END) as total_cuisine_dishes_previous,
                COUNT(DISTINCT CASE WHEN year = {CURRENT_YEAR} THEN dish_id END) as total_cuisine_dishes_current
            FROM ingredient_details
            WHERE cuisine IS NOT NULL
                AND cuisine != ''
            GROUP BY cuisine
        )
        SELECT 
            occ.cuisine,
            occ.total_dish_count as dish_count,
            ROUND(occ.total_dish_count * 100.0 / NULLIF(tid.total_count, 0), 1) as percentage,
            ROUND(gc.count_current * 100.0 / NULLIF(cty.total_cuisine_dishes_current, 0), 1) as current_penetration,
            ROUND(gc.count_previous * 100.0 / NULLIF(cty.total_cuisine_dishes_previous, 0), 1) as previous_penetration,
            CASE 
                WHEN gc.count_previous = 0 OR gc.count_previous IS NULL OR cty.total_cuisine_dishes_previous = 0 THEN 
                    CASE 
                        WHEN gc.count_current > 0 AND cty.total_cuisine_dishes_current > 0 THEN 100.0
                        ELSE 0.0
                    END
                ELSE ROUND(((gc.count_current * 100.0 / NULLIF(cty.total_cuisine_dishes_current, 0)) - 
                           (gc.count_previous * 100.0 / NULLIF(cty.total_cuisine_dishes_previous, 0))) * 
                           100.0 / NULLIF((gc.count_previous * 100.0 / NULLIF(cty.total_cuisine_dishes_previous, 0)), 0), 1)
            END as growth_rate,
            ROUND(occ.total_dish_count * 100.0 / NULLIF(ct.total_cuisine_dishes, 0), 1) as penetration_rate,
            occ.avg_rating,
            COALESCE(gc.count_current, 0) as count_current,
            COALESCE(gc.count_previous, 0) as count_previous
        FROM overall_cuisine_counts occ
        LEFT JOIN growth_counts gc ON occ.cuisine = gc.cuisine
        LEFT JOIN cuisine_totals ct ON occ.cuisine = ct.cuisine
        LEFT JOIN cuisine_totals_by_year cty ON occ.cuisine = cty.cuisine
        CROSS JOIN total_ingredient_dishes tid
        WHERE occ.total_dish_count >= 2  -- Filter out cuisines with very few dishes
        ORDER BY occ.total_dish_count DESC;
        """
        
        result = await execute_query(
            cuisine_analysis_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if not result["rows"]:
            raise HTTPException(status_code=404, detail=f"No cuisine data found for ingredient: {ingredient}")
        
        # Keep original CuisineData for internal calculations
        cuisine_data = []
        
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
                
            except Exception as e:
                print(f"Error processing cuisine row {row}: {e}")
                continue
        
        if not cuisine_data:
            raise HTTPException(status_code=404, detail=f"No valid cuisine data found for ingredient: {ingredient}")
        
        # Calculate total dishes
        total_dishes = sum(c.dish_count for c in cuisine_data)
        
        # Create distribution data (Top 8 + Others) for pie chart
        distribution_data = []
        top_8_cuisines = cuisine_data[:8]
        remaining_cuisines = cuisine_data[8:]
        
        # Add top 8 cuisines
        top_8_percentage_sum = 0
        for i, cuisine in enumerate(top_8_cuisines):
            distribution_data.append(DistributionData(
                name=cuisine.cuisine,
                percentage=cuisine.percentage,
                dish_count=cuisine.dish_count
            ))
            top_8_percentage_sum += cuisine.percentage
        
        # Add "Others" category if there are remaining cuisines
        if remaining_cuisines:
            others_dish_count = sum(c.dish_count for c in remaining_cuisines)
            others_percentage = 100.0 - top_8_percentage_sum
            
            distribution_data.append(DistributionData(
                name="Others",
                percentage=round(others_percentage, 1),
                dish_count=others_dish_count
            ))
        
        # Create penetration data (Top 8 only) for bar chart - sorted by penetration
        penetration_data = []
        sorted_cuisines = sorted(top_8_cuisines, key=lambda x: x.penetration, reverse=True)
        for cuisine in sorted_cuisines:
            # Find the corresponding row to get current and previous penetration
            cuisine_row = next((row for row in result["rows"] if row["cuisine"] == cuisine.cuisine), None)
            current_penetration = float(cuisine_row["current_penetration"]) if cuisine_row and cuisine_row["current_penetration"] is not None else 0.0
            previous_penetration = float(cuisine_row["previous_penetration"]) if cuisine_row and cuisine_row["previous_penetration"] is not None else 0.0
            
            penetration_data.append(PenetrationData(
                name=cuisine.cuisine,
                penetration=current_penetration,
                previous_penetration=previous_penetration,
                growth=cuisine.growth,
                dish_count=cuisine.dish_count
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
            distribution_data=distribution_data,  # Top 8 + Others for pie chart
            penetration_data=penetration_data,    # Top 8 for bar chart
            total_dishes=total_dishes,
            total_cuisines=len(cuisine_data),
            highest_growth_cuisine=highest_growth,
            highest_penetration_cuisine=highest_penetration,
            emerging_cuisines=emerging_cuisines[:5],
            avg_growth_rate=round(avg_growth, 1)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cuisine analysis data")