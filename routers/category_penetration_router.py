# # routers/category_penetration_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import CategoryPenetrationData, CategoryPenetration

# router = APIRouter()

# @router.get("/category-penetration", response_model=CategoryPenetrationData)
# async def get_category_penetration(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"
        
#         # Color palette for categories
#         color_palette = [
#             '#00255a', '#199ef3', '#3179c0', '#5590d6', '#84abdd',
#             '#adc5e5', '#c3d5ec', '#d1e3f6', '#e4eef9', '#f0f6fc'
#         ]
        
#         category_penetration_query = f"""
#         WITH category_counts AS (
#             SELECT 
#                 d.general_category,
#                 COUNT(DISTINCT d.dish_id) AS ingredient_count
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.general_category IS NOT NULL
#             GROUP BY 
#                 d.general_category
#         ),
#         total_counts AS (
#             SELECT 
#                 general_category,
#                 COUNT(DISTINCT dish_id) AS total_count
#             FROM 
#                 flavorlens.main.dishes
#             WHERE 
#                 general_category IS NOT NULL
#             GROUP BY 
#                 general_category
#         ),
#         growth_data AS (
#             SELECT 
#                 d.general_category,
#                 COUNT(DISTINCT CASE WHEN EXTRACT(YEAR FROM d.date_created) >= EXTRACT(YEAR FROM CURRENT_DATE) - 2 
#                       THEN d.dish_id ELSE NULL END) AS recent,
#                 COUNT(DISTINCT CASE WHEN EXTRACT(YEAR FROM d.date_created) < EXTRACT(YEAR FROM CURRENT_DATE) - 2 
#                       THEN d.dish_id ELSE NULL END) AS older
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.general_category IS NOT NULL
#             GROUP BY 
#                 d.general_category
#         )
#         SELECT 
#             cc.general_category AS name,
#             ROUND((cc.ingredient_count * 100.0 / NULLIF(tc.total_count, 0)), 1) AS penetration,
#             CASE
#                 WHEN gd.older = 0 THEN 25.0
#                 WHEN gd.recent > gd.older THEN ROUND((gd.recent - gd.older) * 100.0 / gd.older, 1)
#                 ELSE 5.0
#             END AS growth,
#             CASE
#                 WHEN gd.older = 0 THEN 'Hot'
#                 WHEN gd.recent > gd.older * 1.25 THEN 'Hot'
#                 WHEN gd.recent > gd.older * 1.1 THEN 'Rising'
#                 WHEN gd.recent >= gd.older * 0.9 THEN 'Stable'
#                 ELSE 'Declining'
#             END AS status
#         FROM 
#             category_counts cc
#         JOIN 
#             total_counts tc ON cc.general_category = tc.general_category
#         LEFT JOIN
#             growth_data gd ON cc.general_category = gd.general_category
#         ORDER BY 
#             penetration DESC
#         LIMIT 10;
#         """
        
#         result = await execute_query(
#             category_penetration_query,
#             options=QueryOptions(cacheable=True, ttl=3600000)
#         )
        
#         categories = []
#         if result["rows"]:
#             for index, row in enumerate(result["rows"]):
#                 categories.append(CategoryPenetration(
#                     name=str(row["name"]),
#                     penetration=float(row["penetration"]),
#                     growth=float(row["growth"]),
#                     status=str(row["status"]),
#                     color=color_palette[index % len(color_palette)]
#                 ))
        
#         return CategoryPenetrationData(categories=categories)
        
#     except Exception as e:
#         print(f"Database query error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch category penetration data")


# routers/category_penetration_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import CategoryPenetrationData, CategoryPenetration

router = APIRouter()

@router.get("/category-penetration", response_model=CategoryPenetrationData)
async def get_category_penetration(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Color palette for categories
        color_palette = [
            '#00255a', '#199ef3', '#3179c0', '#5590d6', '#84abdd',
            '#adc5e5', '#c3d5ec', '#d1e3f6', '#e4eef9', '#f0f6fc'
        ]
        
        category_penetration_query = f"""
        WITH category_counts AS (
            SELECT 
                general_category,
                COUNT(*) AS ingredient_count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
            GROUP BY 
                general_category
        ),
        total_counts AS (
            SELECT 
                general_category,
                COUNT(*) AS total_count
            FROM 
                ingredient_details
            WHERE 
                general_category IS NOT NULL
            GROUP BY 
                general_category
        ),
        growth_data AS (
            SELECT 
                general_category,
                COUNT(CASE WHEN EXTRACT(YEAR FROM dish_date_created) >= EXTRACT(YEAR FROM CURRENT_DATE) - 1 
                      THEN 1 ELSE NULL END) AS recent,
                COUNT(CASE WHEN EXTRACT(YEAR FROM dish_date_created) = EXTRACT(YEAR FROM CURRENT_DATE) - 2 
                      THEN 1 ELSE NULL END) AS older
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
            GROUP BY 
                general_category
        )
        SELECT 
            cc.general_category AS name,
            ROUND((cc.ingredient_count * 100.0 / NULLIF(tc.total_count, 0)), 1) AS penetration,
            CASE
                WHEN gd.older = 0 AND gd.recent > 0 THEN 50.0
                WHEN gd.older = 0 THEN 0.0
                ELSE ROUND((gd.recent - gd.older) * 100.0 / NULLIF(gd.older, 0), 1)
            END AS growth,
            CASE
                WHEN gd.older = 0 AND gd.recent > 0 THEN 'Hot'
                WHEN gd.older = 0 THEN 'New'
                WHEN gd.recent > gd.older * 1.25 THEN 'Hot'
                WHEN gd.recent > gd.older * 1.1 THEN 'Rising'
                WHEN gd.recent >= gd.older * 0.9 THEN 'Stable'
                ELSE 'Declining'
            END AS status
        FROM 
            category_counts cc
        JOIN 
            total_counts tc ON cc.general_category = tc.general_category
        LEFT JOIN
            growth_data gd ON cc.general_category = gd.general_category
        ORDER BY 
            penetration DESC
        LIMIT 10;
        """
        
        result = await execute_query(
            category_penetration_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        categories = []
        if result["rows"]:
            for index, row in enumerate(result["rows"]):
                categories.append(CategoryPenetration(
                    name=str(row["name"]),
                    penetration=float(row["penetration"]) if row["penetration"] is not None else 0.0,
                    growth=float(row["growth"]) if row["growth"] is not None else 0.0,
                    status=str(row["status"]),
                    color=color_palette[index % len(color_palette)]
                ))
        
        return CategoryPenetrationData(categories=categories)
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category penetration data")