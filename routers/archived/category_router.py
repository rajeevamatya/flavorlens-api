# routers/category_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
import asyncio

class CategoryDistribution(BaseModel):
    name: str
    value: float
    dish_count: int
    count_2023: int
    yoy_growth_percentage: Optional[float]

class CategoryPenetration(BaseModel):
    name: str
    penetration: float
    growth: float
    status: str

class CategoryPenetrationData(BaseModel):
    categories: List[CategoryPenetration]

class CategoryTrend(BaseModel):
    name: str
    adoption_percentages: List[float]

class CategoryTrendData(BaseModel):
    years: List[int]
    categories: List[CategoryTrend]

router = APIRouter()

@router.get("/category/distribution", response_model=List[CategoryDistribution])
async def get_category_distribution(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        category_distribution_query = f"""
        WITH ingredient_counts AS (
            SELECT 
                general_category,
                year,
                COUNT(*) AS count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
            GROUP BY general_category, year
        ),
        pivoted AS (
            SELECT
                general_category,
                SUM(CASE WHEN year = 2023 THEN count ELSE 0 END) AS count_2023,
                SUM(CASE WHEN year = 2024 THEN count ELSE 0 END) AS count_2024
            FROM ingredient_counts
            GROUP BY general_category
        ),
        total AS (
            SELECT SUM(count_2024) AS total_2024
            FROM pivoted
        )
        SELECT 
            p.general_category AS name,
            p.count_2024 AS dish_count,
            ROUND(p.count_2024 * 100.0 / NULLIF(t.total_2024, 0), 2) AS value,
            p.count_2023,
            ROUND(
                CASE 
                    WHEN p.count_2023 = 0 THEN NULL
                    ELSE ((p.count_2024 - p.count_2023) * 100.0 / p.count_2023)
                END,
                2
            ) AS yoy_growth_percentage
        FROM pivoted p, total t
        WHERE p.general_category IS NOT NULL
        ORDER BY dish_count DESC;
        """
        
        result = await execute_query(
            category_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if result["rows"]:
            categories = []
            for row in result["rows"]:
                categories.append(CategoryDistribution(
                    name=str(row["name"]),
                    value=float(row["value"]) if row["value"] is not None else 0.0,
                    dish_count=int(row["dish_count"]),
                    count_2023=int(row["count_2023"]) if row["count_2023"] is not None else 0,
                    yoy_growth_percentage=float(row["yoy_growth_percentage"]) if row["yoy_growth_percentage"] is not None else None
                ))
            
            return categories
        
        return []
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category distribution data")

@router.get("/category/penetration", response_model=CategoryPenetrationData)
async def get_category_penetration(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        category_penetration_query = f"""
        WITH category_counts AS (
            SELECT 
                general_category,
                COUNT(*) AS ingredient_count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
            GROUP BY general_category
        ),
        total_counts AS (
            SELECT 
                general_category,
                COUNT(*) AS total_count
            FROM ingredient_details
            WHERE general_category IS NOT NULL
            GROUP BY general_category
        ),
        growth_data AS (
            SELECT 
                general_category,
                COUNT(CASE WHEN year = 2024 THEN 1 ELSE NULL END) AS count_2024,
                COUNT(CASE WHEN year = 2023 THEN 1 ELSE NULL END) AS count_2023
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
            GROUP BY general_category
        )
        SELECT 
            cc.general_category AS name,
            ROUND((cc.ingredient_count * 100.0 / NULLIF(tc.total_count, 0)), 1) AS penetration,
            CASE
                WHEN gd.count_2023 = 0 AND gd.count_2024 > 0 THEN 50.0
                WHEN gd.count_2023 = 0 THEN 0.0
                ELSE ROUND((gd.count_2024 - gd.count_2023) * 100.0 / NULLIF(gd.count_2023, 0), 1)
            END AS growth,
            CASE
                WHEN gd.count_2023 = 0 AND gd.count_2024 > 0 THEN 'Hot'
                WHEN gd.count_2023 = 0 THEN 'New'
                WHEN gd.count_2024 > gd.count_2023 * 1.25 THEN 'Hot'
                WHEN gd.count_2024 > gd.count_2023 * 1.1 THEN 'Rising'
                WHEN gd.count_2024 >= gd.count_2023 * 0.9 THEN 'Stable'
                ELSE 'Declining'
            END AS status
        FROM category_counts cc
        JOIN total_counts tc ON cc.general_category = tc.general_category
        LEFT JOIN growth_data gd ON cc.general_category = gd.general_category
        ORDER BY penetration DESC
        LIMIT 10;
        """
        
        result = await execute_query(
            category_penetration_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        categories = []
        if result["rows"]:
            for row in result["rows"]:
                categories.append(CategoryPenetration(
                    name=str(row["name"]),
                    penetration=float(row["penetration"]) if row["penetration"] is not None else 0.0,
                    growth=float(row["growth"]) if row["growth"] is not None else 0.0,
                    status=str(row["status"])
                ))
        
        return CategoryPenetrationData(categories=categories)
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category penetration data")

@router.get("/category/trends", response_model=CategoryTrendData)
async def get_category_trends(ingredient: str = Query(..., description="Ingredient name")):
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
        
        category_trends_query = f"""
        WITH yearly_category_totals AS (
            SELECT 
                year,
                COALESCE(general_category, 'Other') AS category,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND general_category IS NOT NULL
            GROUP BY year, general_category
        ),
        yearly_category_ingredient AS (
            SELECT 
                year,
                COALESCE(general_category, 'Other') AS category,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND general_category IS NOT NULL
            GROUP BY year, general_category
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
            
            return CategoryTrendData(years=years, categories=categories)
        
        return CategoryTrendData(years=[], categories=[])
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category trends data")