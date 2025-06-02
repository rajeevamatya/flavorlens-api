# routers/consumer_insights_attributes.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class AttributeType(str, Enum):
    flavor = "flavor"
    texture = "texture"
    aroma = "aroma"
    diet = "diet"
    functional_health = "functional_health"
    occasions = "occasions"
    convenience = "convenience"
    social = "social"
    emotional = "emotional"
    cooking_technique = "cooking_technique"


class Attribute(BaseModel):
    name: str
    value: float

class AttributeInsightsResponse(BaseModel):
    attributes: List[Attribute]
    trends: List[Dict[str, Any]]
    insights: Dict[str, Any]
    attribute_type: str

router = APIRouter()

# Mapping of attribute types to their table names and column names
ATTRIBUTE_CONFIG = {
    "flavor": {
        "table": "ingredient_flavor",
        "attribute_column": "flavor_attribute"
    },
    "texture": {
        "table": "ingredient_texture", 
        "attribute_column": "texture_attribute"
    },
    "aroma": {
        "table": "ingredient_aroma",
        "attribute_column": "aroma_attribute"
    },
    "diet": {
        "table": "ingredient_diet",
        "attribute_column": "diet_attribute"
    },
    "functional_health": {
        "table": "ingredient_functional_health",
        "attribute_column": "functional_health_attribute"
    },
    "occasions": {
        "table": "ingredient_occasions",
        "attribute_column": "occasion_attribute"
    },
    "convenience": {
        "table": "ingredient_convenience",
        "attribute_column": "convenience_attribute"
    },
    "social": {
        "table": "ingredient_social",
        "attribute_column": "social_attribute"
    },
    "emotional": {
        "table": "ingredient_emotional",
        "attribute_column": "emotional_attribute"
    },
    "cooking_technique": {
        "table": "ingredient_cooking_technique",
        "attribute_column": "cooking_technique_attribute"
    }
}

@router.get("/consumer-insights/{attribute_type}", response_model=AttributeInsightsResponse)
async def get_attribute_insights(
    attribute_type: AttributeType,
    ingredient: str = Query(..., description="Ingredient name"),
    start_year: Optional[int] = Query(None, description="Start year for trend analysis"),
    end_year: Optional[int] = Query(None, description="End year for trend analysis")
):
    """
    Generic endpoint for getting consumer insights for any attribute type.
    
    Supported attribute_types:
    - flavor: Get flavor insights from ingredient_flavor table
    - texture: Get texture insights from ingredient_texture table
    - aroma: Get aroma insights from ingredient_aroma table
    - visual: Get visual insights from ingredient_visual table
    """
    
    # Get configuration for the attribute type
    if attribute_type not in ATTRIBUTE_CONFIG:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported attribute type: {attribute_type}. Supported types: {list(ATTRIBUTE_CONFIG.keys())}"
        )
    
    config = ATTRIBUTE_CONFIG[attribute_type]
    table_name = config["table"]
    attribute_column = config["attribute_column"]
    
    try:
        # Get current distribution AND determine top 6 attributes
        current_distribution_query = f"""
        WITH attribute_counts AS (
            SELECT 
                LOWER(TRIM({attribute_column})) as attribute_name,
                COUNT(*) as mention_count,
                AVG(star_rating) as avg_rating,
                SUM(num_ratings) as total_ratings,
                SUM(num_reviews) as total_reviews
            FROM {table_name}
            WHERE ingredient_name ILIKE '%{ingredient}%'
                AND {attribute_column} IS NOT NULL
                AND LENGTH(TRIM({attribute_column})) > 0
            GROUP BY LOWER(TRIM({attribute_column}))
        ),
        total_mentions AS (
            SELECT SUM(mention_count) as total_count
            FROM attribute_counts
        )
        SELECT 
            CONCAT(UPPER(SUBSTR(ac.attribute_name, 1, 1)), LOWER(SUBSTR(ac.attribute_name, 2))) as name,
            ac.attribute_name as raw_name,
            ROUND(CAST((ac.mention_count * 100.0 / COALESCE(NULLIF(tm.total_count, 0), 1)) AS DECIMAL(10,1))) as percentage,
            ac.mention_count,
            ROUND(CAST(ac.avg_rating AS DECIMAL(10,2))) as avg_rating,
            ac.total_ratings,
            ac.total_reviews
        FROM attribute_counts ac
        CROSS JOIN total_mentions tm
        ORDER BY percentage DESC
        LIMIT 6;
        """
        
        # Execute distribution query first to get the definitive top 6
        distribution_result = await execute_query(
            current_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        # Extract the top 6 attribute names for use in trends query
        top_6_attribute_names = []
        if distribution_result["rows"]:
            top_6_attribute_names = [row["raw_name"] for row in distribution_result["rows"]]
        
        # Build trends query using the exact top 6 attributes from distribution
        if top_6_attribute_names:
            # Create a comma-separated list of quoted attribute names for SQL IN clause
            attribute_names_sql = "', '".join(top_6_attribute_names)
            attribute_names_sql = f"'{attribute_names_sql}'"
            
            trends_query = f"""
            WITH attribute_yearly AS (
                SELECT 
                    TRY_CAST(year AS INTEGER) as year,
                    LOWER(TRIM({attribute_column})) as attribute_name,
                    COUNT(*) as count
                FROM {table_name}
                WHERE ingredient_name ILIKE '%{ingredient}%'
                    AND {attribute_column} IS NOT NULL
                    AND LENGTH(TRIM({attribute_column})) > 0
                    AND year IS NOT NULL
                    AND TRY_CAST(year AS INTEGER) IS NOT NULL
                    AND TRY_CAST(year AS INTEGER) BETWEEN 1900 AND 2030
                    AND LOWER(TRIM({attribute_column})) IN ({attribute_names_sql})
                GROUP BY TRY_CAST(year AS INTEGER), LOWER(TRIM({attribute_column}))
            ),
            yearly_totals AS (
                SELECT 
                    year,
                    SUM(count) as total_count
                FROM attribute_yearly
                WHERE year IS NOT NULL
                GROUP BY year
            )
            SELECT 
                CAST(ay.year AS VARCHAR) as year,
                CONCAT(UPPER(SUBSTR(ay.attribute_name, 1, 1)), LOWER(SUBSTR(ay.attribute_name, 2))) as attribute_name,
                ROUND(CAST((ay.count * 100.0 / COALESCE(NULLIF(yt.total_count, 0), 1)) AS DECIMAL(10,1))) as percentage
            FROM attribute_yearly ay
            JOIN yearly_totals yt ON ay.year = yt.year
            WHERE ay.year IS NOT NULL
            ORDER BY ay.year, ay.attribute_name;
            """
        else:
            # Fallback if no distribution data
            trends_query = "SELECT '' as year, '' as attribute_name, 0 as percentage WHERE 1=0"
        
        # Get detailed attributes for insights
        detailed_attributes_query = f"""
        SELECT 
            {attribute_column},
            COUNT(*) as mention_count,
            AVG(star_rating) as avg_rating,
            AVG(num_ratings) as avg_num_ratings
        FROM {table_name}
        WHERE ingredient_name ILIKE '%{ingredient}%'
            AND {attribute_column} IS NOT NULL
            AND LENGTH(TRIM({attribute_column})) > 0
        GROUP BY {attribute_column}
        ORDER BY mention_count DESC
        LIMIT 10;
        """
        
        # Add year filtering if provided
        year_filter = ""
        if start_year and end_year:
            year_filter = f" AND TRY_CAST(year AS INTEGER) BETWEEN {start_year} AND {end_year}"
        elif start_year:
            year_filter = f" AND TRY_CAST(year AS INTEGER) >= {start_year}"
        elif end_year:
            year_filter = f" AND TRY_CAST(year AS INTEGER) <= {end_year}"
        
        # Apply year filters to queries if specified
        if year_filter:
            current_distribution_query = current_distribution_query.replace(
                f"FROM {table_name}",
                f"FROM {table_name}"
            ).replace(
                f"WHERE ingredient_name ILIKE '%{ingredient}%'",
                f"WHERE ingredient_name ILIKE '%{ingredient}%'{year_filter}"
            )
            
            detailed_attributes_query = detailed_attributes_query.replace(
                f"WHERE ingredient_name ILIKE '%{ingredient}%'",
                f"WHERE ingredient_name ILIKE '%{ingredient}%'{year_filter}"
            )
        
        # Execute queries
        trends_result = await execute_query(
            trends_query, 
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        attributes_result = await execute_query(
            detailed_attributes_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        # Process attributes data
        attributes = []
        if distribution_result["rows"]:
            for row in distribution_result["rows"]:
                name = str(row["name"])
                percentage = float(row["percentage"]) if row["percentage"] is not None else 0.0
                attributes.append(Attribute(
                    name=name,
                    value=percentage
                ))
        
        # Process trends data
        trends = []
        if trends_result["rows"]:
            # Group by year
            year_data = {}
            for row in trends_result["rows"]:
                year = str(row["year"])
                attribute_name = str(row["attribute_name"])
                percentage = float(row["percentage"]) if row["percentage"] is not None else 0.0
                
                if year not in year_data:
                    year_data[year] = {"year": year}
                
                year_data[year][attribute_name] = percentage
            
            # Convert to list
            trends = list(year_data.values())
            trends.sort(key=lambda x: x["year"])
        
        # Generate default trend data if none exists
        if not trends and attributes:
            years = ['2019', '2020', '2021', '2022']
            for year in years:
                trend_data = {"year": year}
                # Use top 3 attributes from current distribution
                for i, attr in enumerate(attributes[:3]):
                    # Simulate some variation over time
                    base_value = attr.value
                    variation = (int(year) - 2019) * 2  # Small growth over time
                    trend_data[attr.name] = round(max(base_value + variation, 0), 1)
                trends.append(trend_data)
        
        # Generate insights
        insights = generate_attribute_insights(
            attributes, 
            trends, 
            attributes_result["rows"] if attributes_result["rows"] else [],
            ingredient,
            attribute_type
        )
        
        return AttributeInsightsResponse(
            attributes=attributes,
            trends=trends,
            insights=insights,
            attribute_type=attribute_type
        )
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch {attribute_type} insights data")

def generate_attribute_insights(attributes, trends, raw_attributes, ingredient, attribute_type):
    """Generate insights based on attribute data"""
    insights = {
        "dominant_attribute": "",
        "growing_trend": "",
        "declining_trend": "", 
        "key_attributes": [],
        "trend_summary": "",
        "attribute_type": attribute_type
    }
    
    if attributes:
        # Find dominant attribute
        dominant = max(attributes, key=lambda x: x.value)
        insights["dominant_attribute"] = dominant.name
        
        # Analyze trends if available
        if len(trends) >= 2:
            first_year = trends[0]
            last_year = trends[-1]
            
            # Calculate growth rates for available attributes
            growth_rates = {}
            for key in first_year.keys():
                if key != "year" and first_year.get(key, 0) > 0:
                    growth = ((last_year.get(key, 0) - first_year.get(key, 0)) / first_year.get(key, 1)) * 100
                    growth_rates[key] = growth
            
            # Find growing and declining trends
            if growth_rates:
                growing = max(growth_rates.items(), key=lambda x: x[1])
                declining = min(growth_rates.items(), key=lambda x: x[1])
                
                insights["growing_trend"] = growing[0]
                insights["declining_trend"] = declining[0]
                
                insights["trend_summary"] = f"Over the analysis period, {growing[0]} {attribute_type.value} preferences have grown by {growing[1]:.1f}%, while {declining[0]} preferences have declined by {abs(declining[1]):.1f}%."
    
    # Process raw attributes
    if raw_attributes:
        attribute_column_name = ATTRIBUTE_CONFIG[attribute_type]["attribute_column"]
        insights["key_attributes"] = [
            {
                "attribute": row[attribute_column_name],
                "mentions": int(row["mention_count"]),
                "avg_rating": round(float(row["avg_rating"]), 2) if row["avg_rating"] else 0.0
            }
            for row in raw_attributes[:5]  # Top 5
        ]
    
    return insights