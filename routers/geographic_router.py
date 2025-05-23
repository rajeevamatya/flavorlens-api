# # routers/geographic_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from database.models import GeographicData, GeographicRegion, RegionalInsight
# from typing import Dict

# router = APIRouter()

# @router.get("/geographic-distribution", response_model=GeographicData)
# async def get_geographic_distribution(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient.lower()}%'"
        
#         country_distribution_query = f"""
#         WITH ingredient_dishes AS (
#             SELECT DISTINCT
#                 d.dish_id,
#                 d.country,
#                 EXTRACT(year FROM d.date_created) AS year
#             FROM 
#                 flavorlens.main.dishes d
#             JOIN 
#                 flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
#             WHERE 
#                 di.name ILIKE {ingredient_pattern}
#                 AND d.country IS NOT NULL
#                 AND d.country != ''
#         ),
#         total_dishes AS (
#             SELECT COUNT(*) AS count FROM ingredient_dishes
#         ),
#         all_countries AS (
#             SELECT
#                 country,
#                 COUNT(*) AS total_count
#             FROM 
#                 ingredient_dishes
#             GROUP BY 
#                 country
#         ),
#         current_year_counts AS (
#             SELECT 
#                 country,
#                 COUNT(*) AS current_count
#             FROM 
#                 ingredient_dishes
#             WHERE 
#                 year = 2024
#             GROUP BY 
#                 country
#         ),
#         previous_year_counts AS (
#             SELECT 
#                 country,
#                 COUNT(*) AS previous_count
#             FROM 
#                 ingredient_dishes
#             WHERE 
#                 year = 2023
#             GROUP BY 
#                 country
#         )
#         SELECT 
#             ac.country,
#             ROUND((ac.total_count * 100.0 / NULLIF((SELECT count FROM total_dishes), 0)), 1) AS adoption,
#             CASE 
#                 WHEN pyc.previous_count IS NULL OR pyc.previous_count = 0 THEN 25
#                 ELSE ROUND(((COALESCE(cyc.current_count, 0) - pyc.previous_count) * 100.0 / 
#                       GREATEST(pyc.previous_count, 1)), 1)
#             END AS growth
#         FROM 
#             all_countries ac
#         LEFT JOIN 
#             current_year_counts cyc ON ac.country = cyc.country
#         LEFT JOIN 
#             previous_year_counts pyc ON ac.country = pyc.country
#         ORDER BY 
#             adoption DESC
#         LIMIT 10;
#         """
        
#         result = await execute_query(country_distribution_query)
        
#         if not result["rows"]:
#             return GeographicData(regions=[], regionalInsights=[])
        
#         # Region mapping for insights
#         region_mapping = {
#             "USA": "North America", "United States": "North America", "Canada": "North America", "Mexico": "North America",
#             "UK": "Europe", "United Kingdom": "Europe", "France": "Europe", "Germany": "Europe", "Italy": "Europe", 
#             "Spain": "Europe", "Netherlands": "Europe", "Belgium": "Europe", "Switzerland": "Europe",
#             "Japan": "Asia", "China": "Asia", "Korea": "Asia", "South Korea": "Asia", "Thailand": "Asia", 
#             "Vietnam": "Asia", "India": "Asia", "Indonesia": "Asia", "Malaysia": "Asia", "Singapore": "Asia",
#             "Brazil": "Latin America", "Argentina": "Latin America", "Chile": "Latin America", "Colombia": "Latin America",
#             "Peru": "Latin America", "Mexico": "Latin America",
#             "Australia": "Oceania", "New Zealand": "Oceania",
#             "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa", "Egypt": "Africa"
#         }
        
#         # Process regions
#         regions = [
#             GeographicRegion(
#                 country=row["country"],
#                 adoption=float(row["adoption"]),
#                 growth=float(row["growth"])
#             ) for row in result["rows"]
#         ]
        
#         # Calculate regional insights
#         regional_data: Dict[str, Dict] = {}
#         for row in result["rows"]:
#             region = region_mapping.get(row["country"], "Other")
#             if region not in regional_data:
#                 regional_data[region] = {"adoption": 0, "growth": 0, "count": 0}
            
#             regional_data[region]["adoption"] += float(row["adoption"])
#             regional_data[region]["growth"] += float(row["growth"])
#             regional_data[region]["count"] += 1
        
#         # Calculate averages for regional insights
#         regional_insights = []
#         for name, data in regional_data.items():
#             regional_insights.append(RegionalInsight(
#                 name=name,
#                 adoption=round((data["adoption"] / data["count"]), 1),
#                 growth=round((data["growth"] / data["count"]), 1)
#             ))
        
#         # Sort by adoption
#         regional_insights.sort(key=lambda x: x.adoption, reverse=True)
        
#         return GeographicData(
#             regions=regions,
#             regionalInsights=regional_insights
#         )
        
#     except Exception as e:
#         print(f"Error in geographic distribution: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch geographic data from database")




# routers/geographic_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import GeographicData, GeographicRegion, RegionalInsight
from typing import Dict

router = APIRouter()

@router.get("/geographic-distribution", response_model=GeographicData)
async def get_geographic_distribution(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient.lower()}%'"
        
        country_distribution_query = f"""
        WITH ingredient_dishes AS (
            SELECT 
                country,
                EXTRACT(YEAR FROM dish_date_created) AS year,
                COUNT(*) AS dish_count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND country IS NOT NULL
                AND country != ''
            GROUP BY 
                country, EXTRACT(YEAR FROM dish_date_created)
        ),
        total_dishes AS (
            SELECT SUM(dish_count) AS total_count FROM ingredient_dishes
        ),
        all_countries AS (
            SELECT
                country,
                SUM(dish_count) AS total_count
            FROM 
                ingredient_dishes
            GROUP BY 
                country
        ),
        current_year_counts AS (
            SELECT 
                country,
                SUM(dish_count) AS current_count
            FROM 
                ingredient_dishes
            WHERE 
                year = 2024
            GROUP BY 
                country
        ),
        previous_year_counts AS (
            SELECT 
                country,
                SUM(dish_count) AS previous_count
            FROM 
                ingredient_dishes
            WHERE 
                year = 2023
            GROUP BY 
                country
        )
        SELECT 
            ac.country,
            ROUND((ac.total_count * 100.0 / NULLIF((SELECT total_count FROM total_dishes), 0)), 1) AS adoption,
            CASE 
                WHEN pyc.previous_count IS NULL OR pyc.previous_count = 0 THEN 
                    CASE WHEN cyc.current_count > 0 THEN 50.0 ELSE 0.0 END
                ELSE ROUND(((COALESCE(cyc.current_count, 0) - pyc.previous_count) * 100.0 / 
                      NULLIF(pyc.previous_count, 0)), 1)
            END AS growth
        FROM 
            all_countries ac
        LEFT JOIN 
            current_year_counts cyc ON ac.country = cyc.country
        LEFT JOIN 
            previous_year_counts pyc ON ac.country = pyc.country
        ORDER BY 
            adoption DESC
        LIMIT 10;
        """
        
        result = await execute_query(
            country_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if not result["rows"]:
            return GeographicData(regions=[], regionalInsights=[])
        
        # Region mapping for insights
        region_mapping = {
            "USA": "North America", "United States": "North America", "Canada": "North America", "Mexico": "North America",
            "UK": "Europe", "United Kingdom": "Europe", "France": "Europe", "Germany": "Europe", "Italy": "Europe", 
            "Spain": "Europe", "Netherlands": "Europe", "Belgium": "Europe", "Switzerland": "Europe", "Austria": "Europe",
            "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe", "Finland": "Europe", "Portugal": "Europe",
            "Japan": "Asia", "China": "Asia", "Korea": "Asia", "South Korea": "Asia", "Thailand": "Asia", 
            "Vietnam": "Asia", "India": "Asia", "Indonesia": "Asia", "Malaysia": "Asia", "Singapore": "Asia",
            "Philippines": "Asia", "Taiwan": "Asia", "Hong Kong": "Asia",
            "Brazil": "Latin America", "Argentina": "Latin America", "Chile": "Latin America", "Colombia": "Latin America",
            "Peru": "Latin America", "Venezuela": "Latin America", "Ecuador": "Latin America", "Uruguay": "Latin America",
            "Australia": "Oceania", "New Zealand": "Oceania",
            "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa", "Egypt": "Africa", "Morocco": "Africa",
            "Ghana": "Africa", "Ethiopia": "Africa"
        }
        
        # Process regions
        regions = [
            GeographicRegion(
                country=str(row["country"]),
                adoption=float(row["adoption"]) if row["adoption"] is not None else 0.0,
                growth=float(row["growth"]) if row["growth"] is not None else 0.0
            ) for row in result["rows"]
        ]
        
        # Calculate regional insights
        regional_data: Dict[str, Dict] = {}
        for row in result["rows"]:
            region = region_mapping.get(row["country"], "Other")
            if region not in regional_data:
                regional_data[region] = {"adoption": 0, "growth": 0, "count": 0}
            
            adoption_val = float(row["adoption"]) if row["adoption"] is not None else 0.0
            growth_val = float(row["growth"]) if row["growth"] is not None else 0.0
            
            regional_data[region]["adoption"] += adoption_val
            regional_data[region]["growth"] += growth_val
            regional_data[region]["count"] += 1
        
        # Calculate averages for regional insights
        regional_insights = []
        for name, data in regional_data.items():
            if data["count"] > 0:  # Avoid division by zero
                regional_insights.append(RegionalInsight(
                    name=name,
                    adoption=round((data["adoption"] / data["count"]), 1),
                    growth=round((data["growth"] / data["count"]), 1)
                ))
        
        # Sort by adoption
        regional_insights.sort(key=lambda x: x.adoption, reverse=True)
        
        return GeographicData(
            regions=regions,
            regionalInsights=regional_insights
        )
        
    except Exception as e:
        print(f"Error in geographic distribution: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch geographic data from database")