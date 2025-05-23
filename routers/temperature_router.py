# # routers/temperature_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import TemperatureDistribution
# from typing import List

# router = APIRouter()

# @router.get("/serving-temperature", response_model=List[TemperatureDistribution])
# async def get_serving_temperature(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient}%'"
        
#         temperature_query = f"""
#         WITH standardized_temps AS (
#             SELECT
#                 d.dish_id,
#                 CASE
#                     WHEN d.serving_temperature ILIKE '%frozen%' THEN 'Frozen'
#                     WHEN d.serving_temperature ILIKE '%cold%' OR d.serving_temperature ILIKE '%chilled%' OR d.serving_temperature ILIKE '%cool%' OR d.serving_temperature ILIKE '%refrigerated%' THEN 'Cold'
#                     WHEN d.serving_temperature ILIKE '%room%' OR d.serving_temperature ILIKE '%ambient%' THEN 'Room Temperature'
#                     WHEN d.serving_temperature ILIKE '%warm%' THEN 'Warm'
#                     WHEN d.serving_temperature ILIKE '%hot%' THEN 'Hot'
#                     WHEN d.serving_temperature IS NULL THEN 'Not Specified'
#                     ELSE 'Not Specified'
#                 END AS standard_temp
#             FROM
#                 flavorlens.main.dishes d
#             JOIN
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE
#                 di.name ILIKE {ingredient_pattern}
#         ),
#         temp_counts AS (
#             SELECT
#                 standard_temp,
#                 COUNT(DISTINCT dish_id) AS dish_count
#             FROM
#                 standardized_temps
#             WHERE
#                 standard_temp != 'Not Specified'
#             GROUP BY
#                 standard_temp
#         ),
#         total AS (
#             SELECT SUM(dish_count) AS total_count FROM temp_counts
#         )
#         SELECT
#             standard_temp AS name,
#             dish_count,
#             ROUND((dish_count * 100.0 / NULLIF((SELECT total_count FROM total), 0)), 1) AS value
#         FROM
#             temp_counts
#         ORDER BY
#             CASE
#                 WHEN standard_temp = 'Frozen' THEN 1
#                 WHEN standard_temp = 'Cold' THEN 2
#                 WHEN standard_temp = 'Room Temperature' THEN 3
#                 WHEN standard_temp = 'Warm' THEN 4
#                 WHEN standard_temp = 'Hot' THEN 5
#                 ELSE 6
#             END
#         """
        
#         result = await execute_query(
#             temperature_query,
#             options=QueryOptions(cacheable=True, ttl=3600000)
#         )
        
#         temperature_colors = {
#             "Frozen": "#86EFAC",
#             "Cold": "#38BDF8",
#             "Room Temperature": "#00255a",
#             "Warm": "#FB923C",
#             "Hot": "#EF4444"
#         }
        
#         standard_temperatures = ['Frozen', 'Cold', 'Room Temperature', 'Warm', 'Hot']
        
#         if result["rows"]:
#             temp_map = {row["name"]: row for row in result["rows"]}
            
#             processed_data = []
#             for temp in standard_temperatures:
#                 temp_data = temp_map.get(temp)
#                 processed_data.append(TemperatureDistribution(
#                     name=temp,
#                     value=float(temp_data["value"]) if temp_data else 0.0,
#                     dish_count=int(temp_data["dish_count"]) if temp_data else 0,
#                     fill=temperature_colors.get(temp, '#6B7280')
#                 ))
            
#             return processed_data
        
#         # Return empty data with standard temperatures
#         return [
#             TemperatureDistribution(
#                 name=temp,
#                 value=0.0,
#                 dish_count=0,
#                 fill=temperature_colors.get(temp, '#6B7280')
#             ) for temp in standard_temperatures
#         ]
        
#     except Exception as e:
#         print(f"Database query error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch serving temperature data")



# routers/temperature_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import TemperatureDistribution
from typing import List

router = APIRouter()

@router.get("/serving-temperature", response_model=List[TemperatureDistribution])
async def get_serving_temperature(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        temperature_query = f"""
        WITH standardized_temps AS (
            SELECT
                CASE
                    WHEN serving_temperature ILIKE '%frozen%' THEN 'Frozen'
                    WHEN serving_temperature ILIKE '%cold%' OR serving_temperature ILIKE '%chilled%' OR serving_temperature ILIKE '%cool%' OR serving_temperature ILIKE '%refrigerated%' THEN 'Cold'
                    WHEN serving_temperature ILIKE '%room%' OR serving_temperature ILIKE '%ambient%' THEN 'Room Temperature'
                    WHEN serving_temperature ILIKE '%warm%' THEN 'Warm'
                    WHEN serving_temperature ILIKE '%hot%' THEN 'Hot'
                    WHEN serving_temperature IS NULL OR serving_temperature = '' THEN 'Not Specified'
                    ELSE 'Not Specified'
                END AS standard_temp
            FROM
                ingredient_details
            WHERE
                ingredient_name ILIKE {ingredient_pattern}
        ),
        temp_counts AS (
            SELECT
                standard_temp,
                COUNT(*) AS dish_count
            FROM
                standardized_temps
            WHERE
                standard_temp != 'Not Specified'
            GROUP BY
                standard_temp
        ),
        total AS (
            SELECT SUM(dish_count) AS total_count FROM temp_counts
        )
        SELECT
            standard_temp AS name,
            dish_count,
            ROUND((dish_count * 100.0 / NULLIF((SELECT total_count FROM total), 0)), 1) AS value
        FROM
            temp_counts
        ORDER BY
            CASE
                WHEN standard_temp = 'Frozen' THEN 1
                WHEN standard_temp = 'Cold' THEN 2
                WHEN standard_temp = 'Room Temperature' THEN 3
                WHEN standard_temp = 'Warm' THEN 4
                WHEN standard_temp = 'Hot' THEN 5
                ELSE 6
            END
        """
        
        result = await execute_query(
            temperature_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        temperature_colors = {
            "Frozen": "#86EFAC",
            "Cold": "#38BDF8",
            "Room Temperature": "#00255a",
            "Warm": "#FB923C",
            "Hot": "#EF4444"
        }
        
        standard_temperatures = ['Frozen', 'Cold', 'Room Temperature', 'Warm', 'Hot']
        
        if result["rows"]:
            temp_map = {row["name"]: row for row in result["rows"]}
            
            processed_data = []
            for temp in standard_temperatures:
                temp_data = temp_map.get(temp)
                processed_data.append(TemperatureDistribution(
                    name=temp,
                    value=float(temp_data["value"]) if temp_data else 0.0,
                    dish_count=int(temp_data["dish_count"]) if temp_data else 0,
                    fill=temperature_colors.get(temp, '#6B7280')
                ))
            
            return processed_data
        
        # Return empty data with standard temperatures
        return [
            TemperatureDistribution(
                name=temp,
                value=0.0,
                dish_count=0,
                fill=temperature_colors.get(temp, '#6B7280')
            ) for temp in standard_temperatures
        ]
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch serving temperature data")