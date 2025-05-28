# routers/subcategory_analysis_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional

class SubcategoryDistribution(BaseModel):
    subcategory: str
    percentage_of_total: float

class SubcategoryPenetration(BaseModel):
    subcategory: str
    penetration_within_category: float
    growth_in_penetration: float
    status: str  # emerging, growing, mature, declining

class SubcategoryPenetrationData(BaseModel):
    subcategories: List[SubcategoryPenetration]

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
        SELECT 
            specific_category AS subcategory,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage_of_total
        FROM ingredient_details
        WHERE ingredient_name ILIKE {ingredient_pattern}
            AND specific_category IS NOT NULL
            AND specific_category != ''
            AND year = 2024
            {category_filter}
        GROUP BY specific_category
        ORDER BY percentage_of_total DESC;
        """
        
        result = await execute_query(
            subcategory_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        print(f"Distribution query result: {result}")  # Debug log
        
        if result["rows"]:
            subcategories = []
            for row in result["rows"]:
                subcategories.append(SubcategoryDistribution(
                    subcategory=str(row["subcategory"]),
                    percentage_of_total=float(row["percentage_of_total"]) if row["percentage_of_total"] is not None else 0.0
                ))
            
            return subcategories
        
        return []
        
    except Exception as e:
        print(f"Database query error: {e}")
        print(f"Query was: {subcategory_distribution_query}")
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
        WITH penetration_2024 AS (
            SELECT 
                specific_category,
                COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} THEN dish_id END) AS ingredient_dishes,
                COUNT(DISTINCT dish_id) AS total_dishes,
                ROUND(
                    COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} THEN dish_id END) * 100.0 / 
                    NULLIF(COUNT(DISTINCT dish_id), 0), 1
                ) AS penetration_2024
            FROM ingredient_details
            WHERE specific_category IS NOT NULL
                AND specific_category != ''
                AND year = 2024
                {category_filter}
            GROUP BY specific_category
            HAVING COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} THEN dish_id END) > 0
        ),
        penetration_2023 AS (
            SELECT 
                specific_category,
                ROUND(
                    COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} THEN dish_id END) * 100.0 / 
                    NULLIF(COUNT(DISTINCT dish_id), 0), 1
                ) AS penetration_2023
            FROM ingredient_details
            WHERE specific_category IS NOT NULL
                AND specific_category != ''
                AND year = 2023
                {category_filter}
            GROUP BY specific_category
        )
        SELECT 
            p24.specific_category AS subcategory,
            p24.penetration_2024 AS penetration_within_category,
            ROUND(p24.penetration_2024 - COALESCE(p23.penetration_2023, 0), 1) AS growth_in_penetration,
            CASE
                WHEN p23.penetration_2023 IS NULL OR p23.penetration_2023 = 0 THEN 'emerging'
                WHEN p24.penetration_2024 > p23.penetration_2023 * 1.1 THEN 'growing'
                WHEN p24.penetration_2024 < p23.penetration_2023 * 0.9 THEN 'declining'
                ELSE 'mature'
            END AS status
        FROM penetration_2024 p24
        LEFT JOIN penetration_2023 p23 ON p24.specific_category = p23.specific_category
        ORDER BY penetration_within_category DESC
        LIMIT 10;
        """
        
        result = await execute_query(
            subcategory_penetration_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        print(f"Penetration query result: {result}")  # Debug log
        
        subcategories = []
        if result["rows"]:
            for row in result["rows"]:
                subcategories.append(SubcategoryPenetration(
                    subcategory=str(row["subcategory"]),
                    penetration_within_category=float(row["penetration_within_category"]) if row["penetration_within_category"] is not None else 0.0,
                    growth_in_penetration=float(row["growth_in_penetration"]) if row["growth_in_penetration"] is not None else 0.0,
                    status=str(row["status"])
                ))
        
        return SubcategoryPenetrationData(subcategories=subcategories)
        
    except Exception as e:
        print(f"Database query error: {e}")
        print(f"Query was: {subcategory_penetration_query}")
        raise HTTPException(status_code=500, detail="Failed to fetch subcategory penetration data")