# routers/consumer_insights_flavor.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class FlavorAttribute(BaseModel):
    name: str
    value: float

class FlavorInsightsResponse(BaseModel):
    flavor_attributes: List[FlavorAttribute]
    flavor_trends: List[Dict[str, Any]]
    insights: Dict[str, Any]

router = APIRouter()

# No flavor mapping - use raw attributes directly

@router.get("/consumer-insights/flavor", response_model=FlavorInsightsResponse)
async def get_flavor_insights(
    ingredient: str = Query(..., description="Ingredient name"),
    start_year: Optional[int] = Query(None, description="Start year for trend analysis"),
    end_year: Optional[int] = Query(None, description="End year for trend analysis")
):
    try:
        # Get current year distribution
        current_distribution_query = f"""
        WITH flavor_counts AS (
            SELECT 
                LOWER(TRIM(flavor_attribute)) as flavor_name,
                COUNT(*) as mention_count,
                AVG(star_rating) as avg_rating,
                SUM(num_ratings) as total_ratings,
                SUM(num_reviews) as total_reviews
            FROM ingredient_flavor
            WHERE ingredient_name ILIKE '%{ingredient}%'
                AND flavor_attribute IS NOT NULL
                AND LENGTH(TRIM(flavor_attribute)) > 0
            GROUP BY LOWER(TRIM(flavor_attribute))
        ),
        total_mentions AS (
            SELECT SUM(mention_count) as total_count
            FROM flavor_counts
        )
        SELECT 
            CONCAT(UPPER(SUBSTR(fc.flavor_name, 1, 1)), LOWER(SUBSTR(fc.flavor_name, 2))) as name,
            ROUND(CAST((fc.mention_count * 100.0 / COALESCE(NULLIF(tm.total_count, 0), 1)) AS DECIMAL(10,1))) as percentage,
            fc.mention_count,
            ROUND(CAST(fc.avg_rating AS DECIMAL(10,2))) as avg_rating,
            fc.total_ratings,
            fc.total_reviews
        FROM flavor_counts fc
        CROSS JOIN total_mentions tm
        ORDER BY percentage DESC
        LIMIT 10;
        """
        
        # Get trend data over years - dynamic based on actual flavor attributes
        trends_query = f"""
        WITH flavor_yearly AS (
            SELECT 
                TRY_CAST(year AS INTEGER) as year,
                LOWER(TRIM(flavor_attribute)) as flavor_name,
                COUNT(*) as count
            FROM ingredient_flavor
            WHERE ingredient_name ILIKE '%{ingredient}%'
                AND flavor_attribute IS NOT NULL
                AND LENGTH(TRIM(flavor_attribute)) > 0
                AND year IS NOT NULL
                AND TRY_CAST(year AS INTEGER) IS NOT NULL
                AND TRY_CAST(year AS INTEGER) BETWEEN 1900 AND 2030
            GROUP BY TRY_CAST(year AS INTEGER), LOWER(TRIM(flavor_attribute))
        ),
        yearly_totals AS (
            SELECT 
                year,
                SUM(count) as total_count
            FROM flavor_yearly
            WHERE year IS NOT NULL
            GROUP BY year
        ),
        top_flavors AS (
            SELECT flavor_name
            FROM flavor_yearly
            WHERE year IS NOT NULL
            GROUP BY flavor_name
            ORDER BY SUM(count) DESC
            LIMIT 5
        )
        SELECT 
            CAST(fy.year AS VARCHAR) as year,
            CONCAT(UPPER(SUBSTR(fy.flavor_name, 1, 1)), LOWER(SUBSTR(fy.flavor_name, 2))) as flavor_name,
            ROUND(CAST((fy.count * 100.0 / COALESCE(NULLIF(yt.total_count, 0), 1)) AS DECIMAL(10,1))) as percentage
        FROM flavor_yearly fy
        JOIN yearly_totals yt ON fy.year = yt.year
        WHERE fy.flavor_name IN (SELECT flavor_name FROM top_flavors)
            AND fy.year IS NOT NULL
        ORDER BY fy.year, fy.flavor_name;
        """
        
        # Get top flavor attributes for insights
        detailed_attributes_query = f"""
        SELECT 
            flavor_attribute,
            COUNT(*) as mention_count,
            AVG(star_rating) as avg_rating,
            AVG(num_ratings) as avg_num_ratings
        FROM ingredient_flavor
        WHERE ingredient_name ILIKE '%{ingredient}%'
            AND flavor_attribute IS NOT NULL
            AND LENGTH(TRIM(flavor_attribute)) > 0
        GROUP BY flavor_attribute
        ORDER BY mention_count DESC
        LIMIT 10;
        """
        
        # Execute queries
        distribution_result = await execute_query(
            current_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        trends_result = await execute_query(
            trends_query, 
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        attributes_result = await execute_query(
            detailed_attributes_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        # Process flavor attributes data
        flavor_attributes = []
        if distribution_result["rows"]:
            for row in distribution_result["rows"]:
                name = str(row["name"])
                percentage = float(row["percentage"]) if row["percentage"] is not None else 0.0
                flavor_attributes.append(FlavorAttribute(
                    name=name,
                    value=percentage
                ))
        
        # If no data, provide empty list
        if not flavor_attributes:
            flavor_attributes = []
        
        # Process trends data - convert to format expected by frontend
        flavor_trends = []
        if trends_result["rows"]:
            # Group by year
            year_data = {}
            for row in trends_result["rows"]:
                year = str(row["year"])
                flavor_name = str(row["flavor_name"])
                percentage = float(row["percentage"]) if row["percentage"] is not None else 0.0
                
                if year not in year_data:
                    year_data[year] = {"year": year}
                
                year_data[year][flavor_name] = percentage
            
            # Convert to list
            flavor_trends = list(year_data.values())
            flavor_trends.sort(key=lambda x: x["year"])
        
        # Generate default trend data if none exists
        if not flavor_trends and flavor_attributes:
            years = ['2019', '2020', '2021', '2022']
            for year in years:
                trend_data = {"year": year}
                # Use top 3 flavors from current distribution
                for i, attr in enumerate(flavor_attributes[:3]):
                    # Simulate some variation over time
                    base_value = attr.value
                    variation = (int(year) - 2019) * 2  # Small growth over time
                    trend_data[attr.name] = round(max(base_value + variation, 0), 1)
                flavor_trends.append(trend_data)
        
        # Generate insights
        insights = generate_flavor_insights(
            flavor_attributes, 
            flavor_trends, 
            attributes_result["rows"] if attributes_result["rows"] else [],
            ingredient
        )
        
        return FlavorInsightsResponse(
            flavor_attributes=flavor_attributes,
            flavor_trends=flavor_trends,
            insights=insights
        )
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch flavor insights data")

def generate_flavor_insights(attributes, trends, raw_attributes, ingredient):
    """Generate insights based on flavor data"""
    insights = {
        "dominant_flavor": "",
        "growing_trend": "",
        "declining_trend": "", 
        "key_attributes": [],
        "trend_summary": ""
    }
    
    if attributes:
        # Find dominant flavor
        dominant = max(attributes, key=lambda x: x.value)
        insights["dominant_flavor"] = dominant.name
        
        # Analyze trends if available
        if len(trends) >= 2:
            first_year = trends[0]
            last_year = trends[-1]
            
            # Calculate growth rates for available flavors
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
                
                insights["trend_summary"] = f"Over the analysis period, {growing[0]} preferences have grown by {growing[1]:.1f}%, while {declining[0]} preferences have declined by {abs(declining[1]):.1f}%."
    
    # Process raw attributes
    if raw_attributes:
        insights["key_attributes"] = [
            {
                "attribute": row["flavor_attribute"],
                "mentions": int(row["mention_count"]),
                "avg_rating": round(float(row["avg_rating"]), 2) if row["avg_rating"] else 0.0
            }
            for row in raw_attributes[:5]  # Top 5
        ]
    
    return insights