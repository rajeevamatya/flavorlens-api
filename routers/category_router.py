# # routers/category_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import CategoryDistribution
# from typing import List

# router = APIRouter()

# @router.get("/category-distribution", response_model=List[CategoryDistribution])
# async def get_category_distribution(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"
        
#         category_distribution_query = f"""
#         WITH ingredient_dishes AS (
#             SELECT DISTINCT
#                 d.dish_id,
#                 d.general_category
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.general_category IS NOT NULL
#         )
#         SELECT 
#             general_category AS name,
#             COUNT(*) AS dish_count,
#             ROUND((COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM ingredient_dishes), 0)), 1) AS value
#         FROM 
#             ingredient_dishes
#         GROUP BY 
#             general_category
#         ORDER BY 
#             value DESC;
#         """
        
#         result = await execute_query(
#             category_distribution_query,
#             options=QueryOptions(cacheable=True, ttl=3600000)
#         )
        
#         if result["rows"]:
#             color_palette = [
#                 '#00255a', '#199ef3', '#3179c0', '#5590d6', '#84abdd',
#                 '#adc5e5', '#c3d5ec', '#d1e3f6', '#e4eef9', '#f0f6fc'
#             ]
            
#             categories = []
#             for index, row in enumerate(result["rows"]):
#                 categories.append(CategoryDistribution(
#                     name=str(row["name"]),
#                     value=float(row["value"]),
#                     dish_count=int(row["dish_count"]),
#                     fill=color_palette[index % len(color_palette)]
#                 ))
            
#             return categories
        
#         return []
        
#     except Exception as e:
#         print(f"Database query error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch category distribution data")




# routers/category_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import CategoryDistribution
from typing import List

router = APIRouter()

@router.get("/category-distribution", response_model=List[CategoryDistribution])
async def get_category_distribution(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        category_distribution_query = f"""
        WITH ingredient_counts AS (
            SELECT 
                general_category,
                EXTRACT(YEAR FROM dish_date_created) AS year,
                COUNT(*) AS count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
            GROUP BY general_category, year, dish_date_created
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
            color_palette = [
                '#00255a', '#199ef3', '#3179c0', '#5590d6', '#84abdd',
                '#adc5e5', '#c3d5ec', '#d1e3f6', '#e4eef9', '#f0f6fc'
            ]
            
            categories = []
            for index, row in enumerate(result["rows"]):
                categories.append(CategoryDistribution(
                    name=str(row["name"]),
                    value=float(row["value"]) if row["value"] is not None else 0.0,
                    dish_count=int(row["dish_count"]),
                    count_2023=int(row["count_2023"]) if row["count_2023"] is not None else 0,
                    yoy_growth_percentage=float(row["yoy_growth_percentage"]) if row["yoy_growth_percentage"] is not None else None,
                    fill=color_palette[index % len(color_palette)]
                ))
            
            return categories
        
        return []
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category distribution data")