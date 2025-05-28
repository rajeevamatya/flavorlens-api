# routers/subcategory_trends_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
import asyncio

class SubcategoryTrend(BaseModel):
    name: str
    adoption_percentages: List[float]

class SubcategoryTrendData(BaseModel):
    years: List[int]
    subcategories: List[SubcategoryTrend]

router = APIRouter()

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