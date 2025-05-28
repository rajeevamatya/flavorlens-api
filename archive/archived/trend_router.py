# routers/trend_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List
import asyncio

class TrendData(BaseModel):
    years: List[int]
    adoption_percentages: List[float]

class CategoryTrend(BaseModel):
    name: str
    adoption_percentages: List[float]

class CategoryData(BaseModel):
    years: List[int]
    categories: List[CategoryTrend]

router = APIRouter()

@router.get("/trend", response_model=TrendData)
async def get_trend(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        trend_query = f"""
        WITH yearly_totals AS (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            GROUP BY year
        ),
        yearly_ingredient AS (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
            GROUP BY year
        )
        SELECT 
            yt.year,
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

        if result["rows"]:
            years = [int(row["year"]) for row in result["rows"]]
            adoption_percentages = [float(row["adoption_percentage"] or 0.0) for row in result["rows"]]
            
            return TrendData(
                years=years,
                adoption_percentages=adoption_percentages
            )

        return TrendData(years=[], adoption_percentages=[])

    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trend data")

@router.get("/category-trends", response_model=CategoryData)
async def get_category_trends(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        years_query = f"""
        SELECT DISTINCT 
            EXTRACT(YEAR FROM dish_date_created)::INTEGER AS year
        FROM ingredient_details
        WHERE EXTRACT(YEAR FROM dish_date_created) >= 2018
            AND EXTRACT(YEAR FROM dish_date_created) <= EXTRACT(YEAR FROM CURRENT_DATE)
        ORDER BY year ASC
        LIMIT 7;
        """
        
        category_trends_query = f"""
        WITH yearly_category_totals AS (
            SELECT 
                EXTRACT(YEAR FROM dish_date_created)::INTEGER AS year,
                COALESCE(general_category, 'Other') AS category,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE EXTRACT(YEAR FROM dish_date_created) >= 2018
                AND EXTRACT(YEAR FROM dish_date_created) <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND general_category IS NOT NULL
            GROUP BY EXTRACT(YEAR FROM dish_date_created), general_category
        ),
        yearly_category_ingredient AS (
            SELECT 
                EXTRACT(YEAR FROM dish_date_created)::INTEGER AS year,
                COALESCE(general_category, 'Other') AS category,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND EXTRACT(YEAR FROM dish_date_created) >= 2018
                AND EXTRACT(YEAR FROM dish_date_created) <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND general_category IS NOT NULL
            GROUP BY EXTRACT(YEAR FROM dish_date_created), general_category
        )
        SELECT 
            yct.year,
            yct.category AS name,
            ROUND(
                COALESCE(yci.ingredient_dishes, 0) * 100.0 / NULLIF(yct.total_dishes, 0), 
                2
            ) AS adoption_percentage
        FROM yearly_category_totals yct
        LEFT JOIN yearly_category_ingredient yci 
            ON yct.year = yci.year AND yct.category = yci.category
        ORDER BY yct.year ASC, adoption_percentage DESC;
        """
        
        # Execute queries
        years_result, trends_result = await asyncio.gather(
            execute_query(years_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(category_trends_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        if years_result["rows"] and trends_result["rows"]:
            years = [int(row["year"]) for row in years_result["rows"]]
            
            # Process trend data by category
            category_map = {}
            
            # Group data by category
            for row in trends_result["rows"]:
                category_name = str(row["name"])
                if category_name not in category_map:
                    category_map[category_name] = {
                        "name": category_name,
                        "adoption_percentages": [0.0] * len(years)
                    }
                
                # Find the index for this year
                year_index = years.index(int(row["year"])) if int(row["year"]) in years else -1
                if year_index >= 0:
                    category_map[category_name]["adoption_percentages"][year_index] = float(row["adoption_percentage"] or 0.0)
            
            # Convert to list and take top 5 categories by total adoption
            sorted_categories = sorted(
                category_map.values(),
                key=lambda x: sum(x["adoption_percentages"]),
                reverse=True
            )[:5]
            
            categories = [
                CategoryTrend(
                    name=category["name"],
                    adoption_percentages=category["adoption_percentages"]
                )
                for category in sorted_categories
            ]
            
            return CategoryData(years=years, categories=categories)
        
        return CategoryData(years=[], categories=[])
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category trends data")