# # routers/subcategory_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import SubcategoryData, SubcategoryTrend
# from typing import List
# import asyncio

# router = APIRouter()

# @router.get("/subcategory-trends", response_model=SubcategoryData)
# async def get_subcategory_trends(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"
        
#         # Color palette for categories
#         color_palette = [
#             '#00255a', '#199ef3', '#3179c0', '#5590d6', '#84abdd',
#             '#adc5e5', '#c3d5ec', '#d1e3f6', '#e4eef9', '#f0f6fc'
#         ]
        
#         years_query = f"""
#         WITH all_years AS (
#             SELECT DISTINCT 
#                 EXTRACT(YEAR FROM date_created)::INTEGER AS year
#             FROM 
#                 flavorlens.main.dishes
#             WHERE 
#                 EXTRACT(YEAR FROM date_created) >= 2018
#                 AND EXTRACT(YEAR FROM date_created) <= EXTRACT(YEAR FROM CURRENT_DATE)
#         )
#         SELECT year
#         FROM all_years
#         ORDER BY year ASC
#         LIMIT 7;
#         """
        
#         subcategory_trends_query = f"""
#         WITH dish_count AS (
#             SELECT 
#                 EXTRACT(YEAR FROM d.date_created)::INTEGER AS year,
#                 COALESCE(d.general_category, 'Other') AS category,
#                 COUNT(DISTINCT d.dish_id) AS dish_count
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND EXTRACT(YEAR FROM d.date_created) >= 2018
#                 AND EXTRACT(YEAR FROM d.date_created) <= EXTRACT(YEAR FROM CURRENT_DATE)
#                 AND d.general_category IS NOT NULL
#             GROUP BY 
#                 year, category
#         )
#         SELECT 
#             dc.year,
#             dc.category AS name,
#             SUM(dc.dish_count) AS count
#         FROM 
#             dish_count dc
#         GROUP BY 
#             dc.year, dc.category
#         ORDER BY 
#             dc.year ASC, SUM(dc.dish_count) DESC;
#         """
        
#         # Execute queries
#         years_result, trends_result = await asyncio.gather(
#             execute_query(years_query, options=QueryOptions(cacheable=True, ttl=3600000)),
#             execute_query(subcategory_trends_query, options=QueryOptions(cacheable=True, ttl=3600000))
#         )
        
#         if years_result["rows"] and trends_result["rows"]:
#             years = [int(row["year"]) for row in years_result["rows"]]
            
#             # Process trend data by category
#             category_map = {}
            
#             # Group data by category
#             for row in trends_result["rows"]:
#                 category_name = row["name"]
#                 if category_name not in category_map:
#                     category_map[category_name] = {
#                         "name": category_name,
#                         "color": "",
#                         "absoluteValues": [0] * len(years)
#                     }
                
#                 # Find the index for this year
#                 year_index = years.index(int(row["year"])) if int(row["year"]) in years else -1
#                 if year_index >= 0:
#                     category_map[category_name]["absoluteValues"][year_index] = int(row["count"])
            
#             # Convert to list and assign colors
#             categories = []
#             sorted_categories = sorted(
#                 category_map.values(),
#                 key=lambda x: sum(x["absoluteValues"]),
#                 reverse=True
#             )[:5]  # Take top 5 categories
            
#             for index, category in enumerate(sorted_categories):
#                 categories.append(SubcategoryTrend(
#                     name=category["name"],
#                     color=color_palette[index % len(color_palette)],
#                     absoluteValues=category["absoluteValues"]
#                 ))
            
#             return SubcategoryData(years=years, categories=categories)
        
#         return SubcategoryData(years=[], categories=[])
        
#     except Exception as e:
#         print(f"Database query error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch subcategory trends data")


# routers/subcategory_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import SubcategoryData, SubcategoryTrend
from typing import List
import asyncio

router = APIRouter()

@router.get("/subcategory-trends", response_model=SubcategoryData)
async def get_subcategory_trends(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Color palette for categories
        color_palette = [
            '#00255a', '#199ef3', '#3179c0', '#5590d6', '#84abdd',
            '#adc5e5', '#c3d5ec', '#d1e3f6', '#e4eef9', '#f0f6fc'
        ]
        
        years_query = f"""
        WITH all_years AS (
            SELECT DISTINCT 
                EXTRACT(YEAR FROM dish_date_created)::INTEGER AS year
            FROM 
                ingredient_details
            WHERE 
                EXTRACT(YEAR FROM dish_date_created) >= 2018
                AND EXTRACT(YEAR FROM dish_date_created) <= EXTRACT(YEAR FROM CURRENT_DATE)
        )
        SELECT year
        FROM all_years
        ORDER BY year ASC
        LIMIT 7;
        """
        
        subcategory_trends_query = f"""
        WITH dish_count AS (
            SELECT 
                EXTRACT(YEAR FROM dish_date_created)::INTEGER AS year,
                COALESCE(general_category, 'Other') AS category,
                COUNT(*) AS dish_count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND EXTRACT(YEAR FROM dish_date_created) >= 2018
                AND EXTRACT(YEAR FROM dish_date_created) <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND general_category IS NOT NULL
            GROUP BY 
                EXTRACT(YEAR FROM dish_date_created), general_category
        )
        SELECT 
            dc.year,
            dc.category AS name,
            SUM(dc.dish_count) AS count
        FROM 
            dish_count dc
        GROUP BY 
            dc.year, dc.category
        ORDER BY 
            dc.year ASC, SUM(dc.dish_count) DESC;
        """
        
        # Execute queries
        years_result, trends_result = await asyncio.gather(
            execute_query(years_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(subcategory_trends_query, options=QueryOptions(cacheable=True, ttl=3600000))
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
                        "color": "",
                        "absoluteValues": [0] * len(years)
                    }
                
                # Find the index for this year
                year_index = years.index(int(row["year"])) if int(row["year"]) in years else -1
                if year_index >= 0:
                    category_map[category_name]["absoluteValues"][year_index] = int(row["count"])
            
            # Convert to list and assign colors
            categories = []
            sorted_categories = sorted(
                category_map.values(),
                key=lambda x: sum(x["absoluteValues"]),
                reverse=True
            )[:5]  # Take top 5 categories
            
            for index, category in enumerate(sorted_categories):
                categories.append(SubcategoryTrend(
                    name=category["name"],
                    color=color_palette[index % len(color_palette)],
                    absoluteValues=category["absoluteValues"]
                ))
            
            return SubcategoryData(years=years, categories=categories)
        
        return SubcategoryData(years=[], categories=[])
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch subcategory trends data")