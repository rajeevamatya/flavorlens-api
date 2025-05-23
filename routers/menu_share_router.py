# # routers/menu_share_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import ShareData

# router = APIRouter()

# @router.get("/menu-share", response_model=ShareData)
# async def get_menu_share(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"
        
#         menu_share_query = f"""
#         WITH ingredient_data AS (
#             SELECT 
#                 (SELECT COUNT(DISTINCT dish_id) FROM flavorlens.main.dishes WHERE source = 'menu') AS total_menus,
#                 COUNT(DISTINCT d.dish_id) AS ingredient_menus,
#                 MAX(d.date_created) AS latest_date,
#                 MIN(d.date_created) AS earliest_date
#             FROM flavorlens.main.dishes d
#             JOIN flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE di.name ILIKE {ingredient_pattern}
#                 AND d.source = 'menu'
#         )
#         SELECT 
#             ROUND((id.ingredient_menus * 100.0 / NULLIF(id.total_menus, 0)), 1) AS menu_share_percent,
#             (
#                 SELECT ROUND((
#                     (id.ingredient_menus * 100.0 / NULLIF(id.total_menus, 0)) - 
#                     ((id.ingredient_menus - COUNT(DISTINCT d.dish_id)) * 100.0 / NULLIF(id.total_menus, 0))
#                 ), 1)
#                 FROM flavorlens.main.dishes d
#                 JOIN flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#                 WHERE di.name ILIKE {ingredient_pattern}
#                     AND d.source = 'menu'
#                     AND d.date_created BETWEEN 
#                         (SELECT earliest_date + ((latest_date - earliest_date)/2) FROM ingredient_data)
#                         AND (SELECT latest_date FROM ingredient_data)
#             ) AS change_percent,
#             (
#                 SELECT 
#                     CASE WHEN (
#                         (id.ingredient_menus * 100.0 / NULLIF(id.total_menus, 0)) - 
#                         ((id.ingredient_menus - COUNT(DISTINCT d.dish_id)) * 100.0 / NULLIF(id.total_menus, 0))
#                     ) > 0 THEN true ELSE false END
#                 FROM flavorlens.main.dishes d
#                 JOIN flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#                 WHERE di.name ILIKE {ingredient_pattern}
#                     AND d.source = 'menu'
#                     AND d.date_created BETWEEN 
#                         (SELECT earliest_date + ((latest_date - earliest_date)/2) FROM ingredient_data)
#                         AND (SELECT latest_date FROM ingredient_data)
#             ) AS is_positive
#         FROM ingredient_data id;
#         """
        
#         result = await execute_query(
#             menu_share_query,
#             options=QueryOptions(cacheable=True, ttl=600000)  # 10 minutes
#         )
        
#         if result["rows"] and result["rows"][0]["menu_share_percent"] is not None:
#             row = result["rows"][0]
#             return ShareData(
#                 recipe_share_percent=float(row["menu_share_percent"]) if row["menu_share_percent"] else 0.0,
#                 change_percent=float(row["change_percent"]) if row["change_percent"] else 0.0,
#                 is_positive=bool(row["is_positive"]) if row["is_positive"] is not None else False
#             )
        
#         return ShareData(recipe_share_percent=0.0, change_percent=0.0, is_positive=False)
        
#     except Exception as e:
#         print(f"Database query error: {e}")
#         return ShareData(recipe_share_percent=0.0, change_percent=0.0, is_positive=False)



# routers/menu_share_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class MenuShare(BaseModel):
    share_percent: float
    change_percent: float
    # is_positive: bool

router = APIRouter()

@router.get("/menu-share", response_model=MenuShare)
async def get_menu_share(ingredient: str = Query(..., description="Ingredient name")):
    try:
        # Safely escape the ingredient parameter
        ingredient_escaped = ingredient.replace("'", "''")  # Escape single quotes
        ingredient_pattern = f"'%{ingredient_escaped}%'"

        menu_share_query = f"""
        SELECT
            ROUND(
                SUM(CASE WHEN year = 2023 THEN ingredient_dish_count END) * 100.0 / 
                NULLIF(SUM(CASE WHEN year = 2023 THEN total_dish_count END), 0), 
                2
            ) AS menu_share_percent,
            ROUND(
                CASE
                    WHEN SUM(CASE WHEN year = 2022 THEN ingredient_dish_count END) = 0 THEN NULL
                    ELSE (
                        SUM(CASE WHEN year = 2023 THEN ingredient_dish_count END) - 
                        SUM(CASE WHEN year = 2022 THEN ingredient_dish_count END)
                    ) * 100.0 / SUM(CASE WHEN year = 2022 THEN ingredient_dish_count END)
                END,
                2
            ) AS change_percent,
            CASE
                WHEN SUM(CASE WHEN year = 2022 THEN ingredient_dish_count END) = 0 THEN NULL
                ELSE (
                    SUM(CASE WHEN year = 2023 THEN ingredient_dish_count END) - 
                    SUM(CASE WHEN year = 2022 THEN ingredient_dish_count END)
                ) > 0
            END AS is_positive
        FROM (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) FILTER (
                    WHERE ingredient_name ILIKE {ingredient_pattern} AND source = 'menu'
                ) AS ingredient_dish_count,
                COUNT(DISTINCT dish_id) FILTER (
                    WHERE source = 'menu'
                ) AS total_dish_count
            FROM flavorlens.main.ingredient_details
            WHERE year IN (2022, 2023)
            GROUP BY year
        ) counts;
        """

        result = await execute_query(
            menu_share_query,
            options=QueryOptions(cacheable=True, ttl=600000)  # 10 minutes
        )

        if result["rows"] and result["rows"][0]["menu_share_percent"] is not None:
            row = result["rows"][0]
            return MenuShare(
                share_percent=float(row["menu_share_percent"]) if row["menu_share_percent"] else 0.0,
                change_percent=float(row["change_percent"]) if row["change_percent"] else 0.0,
            )

        return MenuShare(share_percent=0.0, change_percent=0.0)

    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")