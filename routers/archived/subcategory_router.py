# routers/subcategory_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
import asyncio

class SubcategoryDistribution(BaseModel):
    name: str
    value: float
    dish_count: int
    count_2023: int
    yoy_growth_percentage: Optional[float]

class SubcategoryPenetration(BaseModel):
    name: str
    penetration: float
    growth: float
    status: str

class SubcategoryPenetrationData(BaseModel):
    subcategories: List[SubcategoryPenetration]

class SubcategoryTrend(BaseModel):
    name: str
    adoption_percentages: List[float]

class SubcategoryTrendData(BaseModel):
    years: List[int]
    subcategories: List[SubcategoryTrend]

router = APIRouter()

@router.get("/subcategory/distribution", response_model=List[SubcategoryDistribution])
async def get_subcategory_distribution(
    ingredient: str = Query(..., description="Ingredient name"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        category_filter = f"AND general_category ILIKE '%{category}%'" if category else ""
        
        subcategory_distribution_query = f"""
        WITH ingredient_counts AS (
            SELECT 
                specific_category,
                year,
                COUNT(*) AS count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
            GROUP BY specific_category, year
        ),
        pivoted AS (
            SELECT
                specific_category,
                SUM(CASE WHEN year = 2023 THEN count ELSE 0 END) AS count_2023,
                SUM(CASE WHEN year = 2024 THEN count ELSE 0 END) AS count_2024
            FROM ingredient_counts
            GROUP BY specific_category
        ),
        total AS (
            SELECT SUM(count_2024) AS total_2024
            FROM pivoted
        )
        SELECT 
            p.specific_category AS name,
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
        WHERE p.specific_category IS NOT NULL
        ORDER BY dish_count DESC;
        """
        
        result = await execute_query(
            subcategory_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if result["rows"]:
            subcategories = []
            for row in result["rows"]:
                subcategories.append(SubcategoryDistribution(
                    name=str(row["name"]),
                    value=float(row["value"]) if row["value"] is not None else 0.0,
                    dish_count=int(row["dish_count"]),
                    count_2023=int(row["count_2023"]) if row["count_2023"] is not None else 0,
                    yoy_growth_percentage=float(row["yoy_growth_percentage"]) if row["yoy_growth_percentage"] is not None else None
                ))
            
            return subcategories
        
        return []
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch subcategory distribution data")

@router.get("/subcategory/penetration", response_model=SubcategoryPenetrationData)
async def get_subcategory_penetration(
    ingredient: str = Query(..., description="Ingredient name"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        category_filter = f"AND general_category ILIKE '%{category}%'" if category else ""
        
        subcategory_penetration_query = f"""
        WITH subcategory_counts AS (
            SELECT 
                specific_category,
                COUNT(*) AS ingredient_count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
            GROUP BY specific_category
        ),
        total_counts AS (
            SELECT 
                specific_category,
                COUNT(*) AS total_count
            FROM ingredient_details
            WHERE specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
            GROUP BY specific_category
        ),
        growth_data AS (
            SELECT 
                specific_category,
                COUNT(CASE WHEN year = 2024 THEN 1 ELSE NULL END) AS count_2024,
                COUNT(CASE WHEN year = 2023 THEN 1 ELSE NULL END) AS count_2023
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
            GROUP BY specific_category
        )
        SELECT 
            sc.specific_category AS name,
            ROUND((sc.ingredient_count * 100.0 / NULLIF(tc.total_count, 0)), 1) AS penetration,
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
        FROM subcategory_counts sc
        JOIN total_counts tc ON sc.specific_category = tc.specific_category
        LEFT JOIN growth_data gd ON sc.specific_category = gd.specific_category
        ORDER BY penetration DESC
        LIMIT 10;
        """
        
        result = await execute_query(
            subcategory_penetration_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        subcategories = []
        if result["rows"]:
            for row in result["rows"]:
                subcategories.append(SubcategoryPenetration(
                    name=str(row["name"]),
                    penetration=float(row["penetration"]) if row["penetration"] is not None else 0.0,
                    growth=float(row["growth"]) if row["growth"] is not None else 0.0,
                    status=str(row["status"])
                ))
        
        return SubcategoryPenetrationData(subcategories=subcategories)
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch subcategory penetration data")

@router.get("/subcategory/trends", response_model=SubcategoryTrendData)
async def get_subcategory_trends(
    ingredient: str = Query(..., description="Ingredient name"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        category_filter = f"AND general_category ILIKE '%{category}%'" if category else ""
        
        years_query = f"""
        SELECT DISTINCT year
        FROM ingredient_details
        WHERE year >= 2018
            AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
        ORDER BY year ASC
        LIMIT 7;
        """
        
        subcategory_trends_query = f"""
        WITH yearly_subcategory_totals AS (
            SELECT 
                year,
                specific_category,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
            GROUP BY year, specific_category
        ),
        yearly_subcategory_ingredient AS (
            SELECT 
                year,
                specific_category,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
            GROUP BY year, specific_category
        )
        SELECT 
            yst.year,
            yst.specific_category AS name,
            ROUND(
                COALESCE(ysi.ingredient_dishes, 0) * 100.0 / NULLIF(yst.total_dishes, 0), 
                2
            ) AS adoption_percentage
        FROM yearly_subcategory_totals yst
        LEFT JOIN yearly_subcategory_ingredient ysi 
            ON yst.year = ysi.year AND yst.specific_category = ysi.specific_category
        ORDER BY yst.year ASC, adoption_percentage DESC;
        """
        
        # Execute queries
        years_result, trends_result = await asyncio.gather(
            execute_query(years_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(subcategory_trends_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        if years_result["rows"] and trends_result["rows"]:
            years = [int(row["year"]) for row in years_result["rows"]]
            
            # Process trend data by subcategory
            subcategory_map = {}
            
            # Group data by subcategory
            for row in trends_result["rows"]:
                subcategory_name = str(row["name"])
                if subcategory_name not in subcategory_map:
                    subcategory_map[subcategory_name] = {
                        "name": subcategory_name,
                        "adoption_percentages": [0.0] * len(years)
                    }
                
                # Find the index for this year
                year_index = years.index(int(row["year"])) if int(row["year"]) in years else -1
                if year_index >= 0:
                    subcategory_map[subcategory_name]["adoption_percentages"][year_index] = float(row["adoption_percentage"] or 0.0)
            
            # Convert to list and take top 5 subcategories by total adoption
            sorted_subcategories = sorted(
                subcategory_map.values(),
                key=lambda x: sum(x["adoption_percentages"]),
                reverse=True
            )[:5]
            
            subcategories = [
                SubcategoryTrend(
                    name=subcategory["name"],
                    adoption_percentages=subcategory["adoption_percentages"]
                )
                for subcategory in sorted_subcategories
            ]
            
            return SubcategoryTrendData(years=years, subcategories=subcategories)
        
        return SubcategoryTrendData(years=[], subcategories=[])
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch subcategory trends data")