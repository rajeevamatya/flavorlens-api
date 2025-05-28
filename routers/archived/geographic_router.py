# # routers/geographic_router.py
# from fastapi import APIRouter, HTTPException, Query
# from database.connection import execute_query, QueryOptions
# from pydantic import BaseModel
# from typing import Dict, List

# class GeographicRegion(BaseModel):
#     country: str
#     adoption: float
#     growth: float

# class RegionalInsight(BaseModel):
#     name: str
#     adoption: float
#     growth: float

# class GeographicData(BaseModel):
#     regions: List[GeographicRegion]
#     regionalInsights: List[RegionalInsight]


# router = APIRouter()

# @router.get("/geographic-distribution", response_model=GeographicData)
# async def get_geographic_distribution(ingredient: str = Query(..., description="Ingredient name")):
#     try:
#         ingredient_pattern = f"'%{ingredient.lower()}%'"
        
#         country_distribution_query = f"""
#         WITH ingredient_dishes AS (
#             SELECT 
#                 country,
#                 EXTRACT(YEAR FROM dish_date_created) AS year,
#                 COUNT(*) AS dish_count
#             FROM 
#                 ingredient_details
#             WHERE 
#                 ingredient_name ILIKE {ingredient_pattern}
#                 AND country IS NOT NULL
#                 AND country != ''
#             GROUP BY 
#                 country, EXTRACT(YEAR FROM dish_date_created)
#         ),
#         total_dishes AS (
#             SELECT SUM(dish_count) AS total_count FROM ingredient_dishes
#         ),
#         all_countries AS (
#             SELECT
#                 country,
#                 SUM(dish_count) AS total_count
#             FROM 
#                 ingredient_dishes
#             GROUP BY 
#                 country
#         ),
#         current_year_counts AS (
#             SELECT 
#                 country,
#                 SUM(dish_count) AS current_count
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
#                 SUM(dish_count) AS previous_count
#             FROM 
#                 ingredient_dishes
#             WHERE 
#                 year = 2023
#             GROUP BY 
#                 country
#         )
#         SELECT 
#             ac.country,
#             ROUND((ac.total_count * 100.0 / NULLIF((SELECT total_count FROM total_dishes), 0)), 1) AS adoption,
#             CASE 
#                 WHEN pyc.previous_count IS NULL OR pyc.previous_count = 0 THEN 
#                     CASE WHEN cyc.current_count > 0 THEN 50.0 ELSE 0.0 END
#                 ELSE ROUND(((COALESCE(cyc.current_count, 0) - pyc.previous_count) * 100.0 / 
#                       NULLIF(pyc.previous_count, 0)), 1)
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
        
#         result = await execute_query(
#             country_distribution_query,
#             options=QueryOptions(cacheable=True, ttl=3600000)
#         )
        
#         if not result["rows"]:
#             return GeographicData(regions=[], regionalInsights=[])
        
#         # Region mapping for insights
#         region_mapping = {
#             "USA": "North America", "United States": "North America", "Canada": "North America", "Mexico": "North America",
#             "UK": "Europe", "United Kingdom": "Europe", "France": "Europe", "Germany": "Europe", "Italy": "Europe", 
#             "Spain": "Europe", "Netherlands": "Europe", "Belgium": "Europe", "Switzerland": "Europe", "Austria": "Europe",
#             "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe", "Finland": "Europe", "Portugal": "Europe",
#             "Japan": "Asia", "China": "Asia", "Korea": "Asia", "South Korea": "Asia", "Thailand": "Asia", 
#             "Vietnam": "Asia", "India": "Asia", "Indonesia": "Asia", "Malaysia": "Asia", "Singapore": "Asia",
#             "Philippines": "Asia", "Taiwan": "Asia", "Hong Kong": "Asia",
#             "Brazil": "Latin America", "Argentina": "Latin America", "Chile": "Latin America", "Colombia": "Latin America",
#             "Peru": "Latin America", "Venezuela": "Latin America", "Ecuador": "Latin America", "Uruguay": "Latin America",
#             "Australia": "Oceania", "New Zealand": "Oceania",
#             "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa", "Egypt": "Africa", "Morocco": "Africa",
#             "Ghana": "Africa", "Ethiopia": "Africa"
#         }
        
#         # Process regions
#         regions = [
#             GeographicRegion(
#                 country=str(row["country"]),
#                 adoption=float(row["adoption"]) if row["adoption"] is not None else 0.0,
#                 growth=float(row["growth"]) if row["growth"] is not None else 0.0
#             ) for row in result["rows"]
#         ]
        
#         # Calculate regional insights
#         regional_data: Dict[str, Dict] = {}
#         for row in result["rows"]:
#             region = region_mapping.get(row["country"], "Other")
#             if region not in regional_data:
#                 regional_data[region] = {"adoption": 0, "growth": 0, "count": 0}
            
#             adoption_val = float(row["adoption"]) if row["adoption"] is not None else 0.0
#             growth_val = float(row["growth"]) if row["growth"] is not None else 0.0
            
#             regional_data[region]["adoption"] += adoption_val
#             regional_data[region]["growth"] += growth_val
#             regional_data[region]["count"] += 1
        
#         # Calculate averages for regional insights
#         regional_insights = []
#         for name, data in regional_data.items():
#             if data["count"] > 0:  # Avoid division by zero
#                 regional_insights.append(RegionalInsight(
#                     name=name,
#                     adoption=round((data["adoption"] / data["count"]), 1),
#                     growth=round((data["growth"] / data["count"]), 1)
#                 ))
        
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
from pydantic import BaseModel
from typing import List, Optional
import asyncio

class GeographicDistribution(BaseModel):
    name: str
    value: float
    dish_count: int
    count_2023: int
    yoy_growth_percentage: Optional[float]

class GeographicPenetration(BaseModel):
    name: str
    penetration: float
    growth: float
    status: str

class GeographicPenetrationData(BaseModel):
    countries: List[GeographicPenetration]

class CountryTrend(BaseModel):
    name: str
    adoption_percentages: List[float]

class GeographicTrendData(BaseModel):
    years: List[int]
    countries: List[CountryTrend]

router = APIRouter()

@router.get("/geographic/distribution", response_model=List[GeographicDistribution])
async def get_geographic_distribution(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        geographic_distribution_query = f"""
        WITH ingredient_counts AS (
            SELECT 
                country,
                year,
                COUNT(*) AS count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND country IS NOT NULL
                AND country != ''
            GROUP BY country, year
        ),
        pivoted AS (
            SELECT
                country,
                SUM(CASE WHEN year = 2023 THEN count ELSE 0 END) AS count_2023,
                SUM(CASE WHEN year = 2024 THEN count ELSE 0 END) AS count_2024
            FROM ingredient_counts
            GROUP BY country
        ),
        total AS (
            SELECT SUM(count_2024) AS total_2024
            FROM pivoted
        )
        SELECT 
            p.country AS name,
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
        WHERE p.country IS NOT NULL
        ORDER BY dish_count DESC;
        """
        
        result = await execute_query(
            geographic_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if result["rows"]:
            countries = []
            for row in result["rows"]:
                countries.append(GeographicDistribution(
                    name=str(row["name"]),
                    value=float(row["value"]) if row["value"] is not None else 0.0,
                    dish_count=int(row["dish_count"]),
                    count_2023=int(row["count_2023"]) if row["count_2023"] is not None else 0,
                    yoy_growth_percentage=float(row["yoy_growth_percentage"]) if row["yoy_growth_percentage"] is not None else None
                ))
            
            return countries
        
        return []
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch geographic distribution data")

@router.get("/geographic/penetration", response_model=GeographicPenetrationData)
async def get_geographic_penetration(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        geographic_penetration_query = f"""
        WITH country_counts AS (
            SELECT 
                country,
                COUNT(*) AS ingredient_count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND country IS NOT NULL
                AND country != ''
            GROUP BY country
        ),
        total_counts AS (
            SELECT 
                country,
                COUNT(*) AS total_count
            FROM ingredient_details
            WHERE country IS NOT NULL
                AND country != ''
            GROUP BY country
        ),
        growth_data AS (
            SELECT 
                country,
                COUNT(CASE WHEN year = 2024 THEN 1 ELSE NULL END) AS count_2024,
                COUNT(CASE WHEN year = 2023 THEN 1 ELSE NULL END) AS count_2023
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND country IS NOT NULL
                AND country != ''
            GROUP BY country
        )
        SELECT 
            cc.country AS name,
            ROUND((cc.ingredient_count * 100.0 / NULLIF(tc.total_count, 0)), 1) AS penetration,
            CASE
                WHEN gd.count_2023 = 0 AND gd.count_2024 > 0 THEN 50.0
                WHEN gd.count_2023 = 0 THEN 0.0
                ELSE ROUND((gd.count_2024 - gd.count_2023) * 100.0 / NULLIF(gd.count_2023, 0), 1)
            END AS growth,
            CASE
                WHEN gd.count_2023 = 0 AND gd.count_2024 > 0 THEN 'Hot'
                WHEN gd.count_2023 = 0 THEN 'New'
                WHEN gd.count_2024 > gd.count_2023 * 1.25 THEN 'Hot'
                WHEN gd.count_2024 > gd.count_2023 * 1.1 THEN 'Rising'
                WHEN gd.count_2024 >= gd.count_2023 * 0.9 THEN 'Stable'
                ELSE 'Declining'
            END AS status
        FROM country_counts cc
        JOIN total_counts tc ON cc.country = tc.country
        LEFT JOIN growth_data gd ON cc.country = gd.country
        ORDER BY penetration DESC
        LIMIT 10;
        """
        
        result = await execute_query(
            geographic_penetration_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        countries = []
        if result["rows"]:
            for row in result["rows"]:
                countries.append(GeographicPenetration(
                    name=str(row["name"]),
                    penetration=float(row["penetration"]) if row["penetration"] is not None else 0.0,
                    growth=float(row["growth"]) if row["growth"] is not None else 0.0,
                    status=str(row["status"])
                ))
        
        return GeographicPenetrationData(countries=countries)
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch geographic penetration data")

@router.get("/geographic/trends", response_model=GeographicTrendData)
async def get_geographic_trends(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        years_query = f"""
        SELECT DISTINCT year
        FROM ingredient_details
        WHERE year >= 2018
            AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
        ORDER BY year ASC
        LIMIT 7;
        """
        
        geographic_trends_query = f"""
        WITH yearly_country_totals AS (
            SELECT 
                year,
                country,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND country IS NOT NULL
                AND country != ''
            GROUP BY year, country
        ),
        yearly_country_ingredient AS (
            SELECT 
                year,
                country,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND country IS NOT NULL
                AND country != ''
            GROUP BY year, country
        )
        SELECT 
            yct.year,
            yct.country AS name,
            ROUND(
                COALESCE(yci.ingredient_dishes, 0) * 100.0 / NULLIF(yct.total_dishes, 0), 
                2
            ) AS adoption_percentage
        FROM yearly_country_totals yct
        LEFT JOIN yearly_country_ingredient yci 
            ON yct.year = yci.year AND yct.country = yci.country
        ORDER BY yct.year ASC, adoption_percentage DESC;
        """
        
        # Execute queries
        years_result, trends_result = await asyncio.gather(
            execute_query(years_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(geographic_trends_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        if years_result["rows"] and trends_result["rows"]:
            years = [int(row["year"]) for row in years_result["rows"]]
            
            # Process trend data by country
            country_map = {}
            
            # Group data by country
            for row in trends_result["rows"]:
                country_name = str(row["name"])
                if country_name not in country_map:
                    country_map[country_name] = {
                        "name": country_name,
                        "adoption_percentages": [0.0] * len(years)
                    }
                
                # Find the index for this year
                year_index = years.index(int(row["year"])) if int(row["year"]) in years else -1
                if year_index >= 0:
                    country_map[country_name]["adoption_percentages"][year_index] = float(row["adoption_percentage"] or 0.0)
            
            # Convert to list and take top 5 countries by total adoption
            sorted_countries = sorted(
                country_map.values(),
                key=lambda x: sum(x["adoption_percentages"]),
                reverse=True
            )[:5]
            
            countries = [
                CountryTrend(
                    name=country["name"],
                    adoption_percentages=country["adoption_percentages"]
                )
                for country in sorted_countries
            ]
            
            return GeographicTrendData(years=years, countries=countries)
        
        return GeographicTrendData(years=[], countries=[])
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch geographic trends data")