# routers/subcategory_distribution_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional

class SubcategoryDistribution(BaseModel):
    subcategory: str
    percentage_of_total: float


router = APIRouter()

@router.get("/subcategory/analysis", response_model=List[SubcategoryDistribution])
async def get_subcategory_distribution(
    ingredient: str = Query(..., description="Ingredient name"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    try:
        # Fix the string formatting for DuckDB
        category_filter = f"AND general_category ILIKE '%{category}%'" if category else ""
        
        subcategory_distribution_query = f"""
        SELECT 
            specific_category AS subcategory,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage_of_total
        FROM ingredient_details
        WHERE ingredient_name ILIKE '%{ingredient}%'
            AND specific_category IS NOT NULL
            AND specific_category != ''
            {category_filter}
        GROUP BY specific_category
        ORDER BY percentage_of_total DESC;
        """
        
        print(f"Executing query: {subcategory_distribution_query}")  # Debug log
        
        result = await execute_query(
            subcategory_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        print(f"Distribution query result: {result}")  # Debug log
        
        if result and "rows" in result and result["rows"]:
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