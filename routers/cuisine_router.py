# # routers/cuisine_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import CuisineDistribution
# from typing import List

# router = APIRouter()

# @router.get("/cuisine-distribution", response_model=List[CuisineDistribution])
# async def get_cuisine_distribution(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"
        
#         cuisine_distribution_query = f"""
#         WITH ingredient_dishes AS (
#             SELECT DISTINCT
#                 d.dish_id,
#                 d.cuisine
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.cuisine IS NOT NULL
#         ),
#         cuisine_growth AS (
#             SELECT 
#                 d.cuisine,
#                 COUNT(DISTINCT CASE WHEN d.date_created >= CURRENT_DATE - INTERVAL '1 year' THEN d.dish_id ELSE NULL END) AS recent_dishes,
#                 COUNT(DISTINCT CASE WHEN d.date_created < CURRENT_DATE - INTERVAL '1 year' AND d.date_created >= CURRENT_DATE - INTERVAL '2 years' THEN d.dish_id ELSE NULL END) AS previous_dishes
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.cuisine IS NOT NULL
#             GROUP BY
#                 d.cuisine
#         )
#         SELECT 
#             id.cuisine,
#             ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ingredient_dishes), 1) AS percentage,
#             COALESCE(
#                 CASE 
#                     WHEN cg.previous_dishes = 0 THEN 10.0
#                     ELSE ROUND((cg.recent_dishes - cg.previous_dishes) * 100.0 / GREATEST(cg.previous_dishes, 1), 1)
#                 END,
#                 0.0
#             ) AS growth,
#             ROUND(COUNT(*) * 100.0 / 
#                 GREATEST((SELECT COUNT(*) FROM flavorlens.main.dishes WHERE cuisine = id.cuisine AND dish_id IN 
#                   (SELECT dish_id FROM flavorlens.main.dish_ingredients)
#                 ), 1), 
#               1) AS adoption
#         FROM 
#             ingredient_dishes id
#         LEFT JOIN
#             cuisine_growth cg ON id.cuisine = cg.cuisine
#         GROUP BY 
#             id.cuisine, cg.recent_dishes, cg.previous_dishes
#         ORDER BY 
#             percentage DESC;
#         """
        
#         result = await execute_query(cuisine_distribution_query)
        
#         cuisines = []
#         if result["rows"]:
#             for row in result["rows"]:
#                 cuisines.append(CuisineDistribution(
#                     cuisine=row["cuisine"],
#                     percentage=float(row["percentage"]),
#                     growth=float(row["growth"]),
#                     adoption=float(row["adoption"])
#                 ))
        
#         return cuisines
        
#     except Exception as e:
#         print(f"Database query error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch cuisine distribution data")


# routers/cuisine_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import CuisineDistribution
from typing import List

router = APIRouter()

@router.get("/cuisine-distribution", response_model=List[CuisineDistribution])
async def get_cuisine_distribution(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        cuisine_distribution_query = f"""
        WITH ingredient_counts AS (
            SELECT 
                cuisine,
                EXTRACT(YEAR FROM dish_date_created) AS year,
                COUNT(*) AS count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
              AND cuisine IS NOT NULL
            GROUP BY cuisine, EXTRACT(YEAR FROM dish_date_created)
        ),
        pivoted AS (
            SELECT
                cuisine,
                SUM(CASE WHEN year = 2023 THEN count ELSE 0 END) AS count_2023,
                SUM(CASE WHEN year = 2024 THEN count ELSE 0 END) AS count_2024
            FROM ingredient_counts
            GROUP BY cuisine
        ),
        total AS (
            SELECT SUM(count_2024) AS total_2024
            FROM pivoted
        ),
        cuisine_adoption AS (
            SELECT 
                cuisine,
                COUNT(*) AS total_ingredient_dishes,
                (SELECT COUNT(*) 
                 FROM ingredient_details id2 
                 WHERE id2.cuisine = id1.cuisine) AS total_cuisine_dishes
            FROM ingredient_details id1
            WHERE ingredient_name ILIKE {ingredient_pattern}
              AND cuisine IS NOT NULL
            GROUP BY cuisine
        )
        SELECT 
            p.cuisine,
            p.count_2024 AS dish_count,
            ROUND(p.count_2024 * 100.0 / NULLIF(t.total_2024, 0), 1) AS percentage,
            ROUND(
                CASE 
                    WHEN p.count_2023 = 0 THEN NULL
                    ELSE ((p.count_2024 - p.count_2023) * 100.0 / p.count_2023)
                END,
                1
            ) AS growth,
            ROUND(
                ca.total_ingredient_dishes * 100.0 / NULLIF(ca.total_cuisine_dishes, 0), 1
            ) AS adoption
        FROM pivoted p
        CROSS JOIN total t
        LEFT JOIN cuisine_adoption ca ON p.cuisine = ca.cuisine
        WHERE p.cuisine IS NOT NULL
        ORDER BY dish_count DESC;
        """
        
        result = await execute_query(
            cuisine_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        cuisines = []
        if result["rows"]:
            for row in result["rows"]:
                cuisines.append(CuisineDistribution(
                    cuisine=str(row["cuisine"]),
                    dish_count=int(row["dish_count"]),
                    percentage=float(row["percentage"]) if row["percentage"] is not None else 0.0,
                    growth=float(row["growth"]) if row["growth"] is not None else None,
                    adoption=float(row["adoption"]) if row["adoption"] is not None else 0.0
                ))
        
        return cuisines
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cuisine distribution data")