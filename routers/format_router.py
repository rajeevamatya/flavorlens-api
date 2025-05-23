# # routers/format_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import FormatData, Format, PopularApplication
# from typing import List

# router = APIRouter()

# @router.get("/format-adoption", response_model=FormatData)
# async def get_format_adoption(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"
        
#         format_adoption_query = f"""
#         WITH total_count AS (
#             SELECT 
#                 COUNT(DISTINCT d.dish_id) AS total
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#         ),
#         ingredient_formats AS (
#             SELECT 
#                 di.format,
#                 COUNT(DISTINCT d.dish_id) AS dish_count
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND di.format IS NOT NULL
#                 AND di.format != ''
#             GROUP BY
#                 di.format
#         ),
#         dish_formats AS (
#             SELECT 
#                 d.food_format AS format,
#                 COUNT(DISTINCT d.dish_id) AS dish_count
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.food_format IS NOT NULL
#                 AND d.food_format != ''
#             GROUP BY
#                 d.food_format
#         ),
#         combined_formats AS (
#             SELECT * FROM ingredient_formats
#             UNION ALL
#             SELECT * FROM dish_formats
#         ),
#         format_applications AS (
#             SELECT 
#                 di.format,
#                 d.specific_category,
#                 COUNT(DISTINCT d.dish_id) AS app_count,
#                 ROW_NUMBER() OVER (PARTITION BY di.format ORDER BY COUNT(DISTINCT d.dish_id) DESC) as rn
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND di.format IS NOT NULL
#                 AND di.format != ''
#                 AND d.specific_category IS NOT NULL
#             GROUP BY
#                 di.format, d.specific_category
#         ),
#         format_summary AS (
#             SELECT
#                 cf.format,
#                 SUM(cf.dish_count) AS dish_count,
#                 ROUND(SUM(cf.dish_count) * 100.0 / (SELECT total FROM total_count), 1) AS adoption
#             FROM
#                 combined_formats cf
#             GROUP BY
#                 cf.format
#         )
#         SELECT 
#             fs.format,
#             fs.adoption,
#             fs.dish_count,
#             ARRAY_AGG(fa.specific_category) FILTER (WHERE fa.rn <= 3) AS top_applications
#         FROM 
#             format_summary fs
#         LEFT JOIN
#             format_applications fa ON fs.format = fa.format
#         GROUP BY
#             fs.format, fs.adoption, fs.dish_count
#         ORDER BY 
#             fs.adoption DESC
#         LIMIT 10;
#         """
        
#         popular_applications_query = f"""
#         WITH ingredient_applications AS (
#             SELECT 
#                 d.specific_category,
#                 COUNT(DISTINCT d.dish_id) AS dish_count
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.specific_category IS NOT NULL
#             GROUP BY
#                 d.specific_category
#         )
#         SELECT 
#             specific_category,
#             dish_count,
#             ROW_NUMBER() OVER (ORDER BY dish_count DESC) as rank
#         FROM 
#             ingredient_applications
#         ORDER BY 
#             dish_count DESC
#         LIMIT 10;
#         """
        
#         # Execute both queries
#         format_result, applications_result = await asyncio.gather(
#             execute_query(format_adoption_query, options=QueryOptions(cacheable=True, ttl=3600000)),
#             execute_query(popular_applications_query, options=QueryOptions(cacheable=True, ttl=3600000))
#         )
        
#         # Process format results
#         formats = []
#         if format_result["rows"]:
#             for row in format_result["rows"]:
#                 formats.append(Format(
#                     format=row["format"],
#                     adoption=float(row["adoption"]),
#                     dish_count=int(row["dish_count"]),
#                     top_applications=row["top_applications"] if row["top_applications"] else []
#                 ))
        
#         # Process applications results
#         popular_applications = []
#         if applications_result["rows"]:
#             for row in applications_result["rows"]:
#                 popular_applications.append(PopularApplication(
#                     name=row["specific_category"],
#                     count=int(row["dish_count"]),
#                     rank=int(row["rank"])
#                 ))
        
#         return FormatData(
#             formats=formats,
#             popularApplications=popular_applications
#         )
        
#     except Exception as e:
#         print(f"Database query error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch format adoption data")



# routers/format_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import FormatData, Format, PopularApplication
from typing import List
import asyncio

router = APIRouter()

@router.get("/format-adoption", response_model=FormatData)
async def get_format_adoption(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        format_adoption_query = f"""
        WITH total_count AS (
            SELECT 
                COUNT(*) AS total
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
        ),
        ingredient_formats AS (
            SELECT 
                ingredient_format AS format,
                COUNT(*) AS dish_count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND ingredient_format IS NOT NULL
                AND ingredient_format != ''
            GROUP BY
                ingredient_format
        ),
        dish_formats AS (
            SELECT 
                food_format AS format,
                COUNT(*) AS dish_count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND food_format IS NOT NULL
                AND food_format != ''
            GROUP BY
                food_format
        ),
        combined_formats AS (
            SELECT * FROM ingredient_formats
            UNION ALL
            SELECT * FROM dish_formats
        ),
        format_applications AS (
            SELECT 
                ingredient_format AS format,
                specific_category,
                COUNT(*) AS app_count,
                ROW_NUMBER() OVER (PARTITION BY ingredient_format ORDER BY COUNT(*) DESC) as rn
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND ingredient_format IS NOT NULL
                AND ingredient_format != ''
                AND specific_category IS NOT NULL
            GROUP BY
                ingredient_format, specific_category
        ),
        format_summary AS (
            SELECT
                cf.format,
                SUM(cf.dish_count) AS dish_count,
                ROUND(SUM(cf.dish_count) * 100.0 / NULLIF((SELECT total FROM total_count), 0), 1) AS adoption
            FROM
                combined_formats cf
            GROUP BY
                cf.format
        )
        SELECT 
            fs.format,
            fs.adoption,
            fs.dish_count,
            ARRAY_AGG(fa.specific_category ORDER BY fa.app_count DESC) FILTER (WHERE fa.rn <= 3) AS top_applications
        FROM 
            format_summary fs
        LEFT JOIN
            format_applications fa ON fs.format = fa.format
        GROUP BY
            fs.format, fs.adoption, fs.dish_count
        ORDER BY 
            fs.adoption DESC
        LIMIT 10;
        """
        
        popular_applications_query = f"""
        WITH ingredient_applications AS (
            SELECT 
                specific_category,
                COUNT(*) AS dish_count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND specific_category IS NOT NULL
            GROUP BY
                specific_category
        )
        SELECT 
            specific_category,
            dish_count,
            ROW_NUMBER() OVER (ORDER BY dish_count DESC) as rank
        FROM 
            ingredient_applications
        ORDER BY 
            dish_count DESC
        LIMIT 10;
        """
        
        # Execute both queries
        format_result, applications_result = await asyncio.gather(
            execute_query(format_adoption_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(popular_applications_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        # Process format results
        formats = []
        if format_result["rows"]:
            for row in format_result["rows"]:
                # Handle top_applications which might be None or an array
                top_apps = []
                if row["top_applications"]:
                    if isinstance(row["top_applications"], list):
                        top_apps = [app for app in row["top_applications"] if app is not None]
                    else:
                        # In case it's a single value or string
                        top_apps = [str(row["top_applications"])]
                
                formats.append(Format(
                    format=str(row["format"]),
                    adoption=float(row["adoption"]) if row["adoption"] is not None else 0.0,
                    dish_count=int(row["dish_count"]) if row["dish_count"] is not None else 0,
                    top_applications=top_apps
                ))
        
        # Process applications results
        popular_applications = []
        if applications_result["rows"]:
            for row in applications_result["rows"]:
                popular_applications.append(PopularApplication(
                    name=str(row["specific_category"]),
                    count=int(row["dish_count"]) if row["dish_count"] is not None else 0,
                    rank=int(row["rank"]) if row["rank"] is not None else 0
                ))
        
        return FormatData(
            formats=formats,
            popularApplications=popular_applications
        )
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch format adoption data")