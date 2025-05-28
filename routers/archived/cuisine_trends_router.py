# routers/cuisine_trends_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
import asyncio


class CuisineTrend(BaseModel):
    name: str
    adoption_percentages: List[float]

class CuisineTrendData(BaseModel):
    years: List[int]
    cuisines: List[CuisineTrend]

router = APIRouter()


@router.get("/cuisine/trends", response_model=CuisineTrendData)
async def get_cuisine_trends(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        years_query = f"""
        SELECT DISTINCT year
        FROM ingredient_details
        WHERE year >= 2018
            AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
        ORDER BY year ASC
        LIMIT 7;
        """
        
        cuisine_trends_query = f"""
        WITH yearly_cuisine_totals AS (
            SELECT 
                year,
                cuisine,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND cuisine IS NOT NULL
                AND cuisine != ''
            GROUP BY year, cuisine
        ),
        yearly_cuisine_ingredient AS (
            SELECT 
                year,
                cuisine,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND cuisine IS NOT NULL
                AND cuisine != ''
            GROUP BY year, cuisine
        )
        SELECT 
            yct.year,
            yct.cuisine AS name,
            ROUND(
                COALESCE(yci.ingredient_dishes, 0) * 100.0 / NULLIF(yct.total_dishes, 0), 
                2
            ) AS adoption_percentage
        FROM yearly_cuisine_totals yct
        LEFT JOIN yearly_cuisine_ingredient yci 
            ON yct.year = yci.year AND yct.cuisine = yci.cuisine
        ORDER BY yct.year ASC, adoption_percentage DESC;
        """
        
        # Execute queries
        years_result, trends_result = await asyncio.gather(
            execute_query(years_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(cuisine_trends_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        if years_result["rows"] and trends_result["rows"]:
            years = [int(row["year"]) for row in years_result["rows"]]
            
            # Process trend data by cuisine
            cuisine_map = {}
            
            # Group data by cuisine
            for row in trends_result["rows"]:
                cuisine_name = str(row["name"])
                if cuisine_name not in cuisine_map:
                    cuisine_map[cuisine_name] = {
                        "name": cuisine_name,
                        "adoption_percentages": [0.0] * len(years)
                    }
                
                # Find the index for this year
                year_index = years.index(int(row["year"])) if int(row["year"]) in years else -1
                if year_index >= 0:
                    cuisine_map[cuisine_name]["adoption_percentages"][year_index] = float(row["adoption_percentage"] or 0.0)
            
            # Convert to list and take top 5 cuisines by total adoption
            sorted_cuisines = sorted(
                cuisine_map.values(),
                key=lambda x: sum(x["adoption_percentages"]),
                reverse=True
            )[:5]
            
            cuisines = [
                CuisineTrend(
                    name=cuisine["name"],
                    adoption_percentages=cuisine["adoption_percentages"]
                )
                for cuisine in sorted_cuisines
            ]
            
            return CuisineTrendData(years=years, cuisines=cuisines)
        
        return CuisineTrendData(years=[], cuisines=[])
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cuisine trends data")