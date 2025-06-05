# routers/season_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional

class SeasonDistribution(BaseModel):
    name: str
    value: float

class SeasonAnalysis(BaseModel):
    peak_season: str
    peak_value: float
    lowest_season: str
    lowest_value: float
    seasonal_variation: float
    year_round_appeal: float
    seasonality_index: str  # 'Low', 'Moderate', 'High'
    is_seasonal_ingredient: bool
    all_season_usage: float
    total_dishes_analyzed: int
    dishes_with_season_data: int
    dishes_without_season_data: int

class SeasonResponse(BaseModel):
    ingredient: str
    distribution: List[SeasonDistribution]
    analysis: SeasonAnalysis
    summary: str

router = APIRouter()

@router.get("/season/distribution", response_model=SeasonResponse)
async def get_season_distribution(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # First, let's debug what seasons actually exist in the data
        debug_query = f"""
        SELECT DISTINCT 
            season,
            UPPER(TRIM(season)) as normalized_season,
            COUNT(DISTINCT dish_id) as dish_count
        FROM ingredient_details
        WHERE ingredient_name ILIKE {ingredient_pattern}
            AND season IS NOT NULL
            AND TRIM(season) != ''
        GROUP BY season
        ORDER BY dish_count DESC;
        """
        
        debug_result = await execute_query(debug_query)
        print(f"Available seasons for {ingredient}: {debug_result['rows'] if debug_result['rows'] else 'No season data'}")
        
        # Query with case-insensitive season matching - calculate against only dishes with season data
        seasonal_query = f"""
        WITH total_ingredient_dishes AS (
            -- Get total dishes containing this ingredient across all data
            SELECT COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
        ),
        seasoned_ingredient_dishes AS (
            -- Get total dishes containing this ingredient that have season data
            SELECT COUNT(DISTINCT dish_id) AS total_seasoned_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND season IS NOT NULL
                AND TRIM(season) != ''
        ),
        ingredient_by_season AS (
            SELECT 
                CASE 
                    WHEN LOWER(TRIM(season)) = 'spring' THEN 'Spring'
                    WHEN LOWER(TRIM(season)) = 'summer' THEN 'Summer'
                    WHEN LOWER(TRIM(season)) = 'fall' THEN 'Fall'
                    WHEN LOWER(TRIM(season)) = 'winter' THEN 'Winter'
                    WHEN LOWER(TRIM(season)) = 'all-season' THEN 'All-Season'
                    ELSE NULL  -- Don't categorize unknown seasons
                END AS normalized_season,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND season IS NOT NULL
                AND TRIM(season) != ''
            GROUP BY 
                CASE 
                    WHEN LOWER(TRIM(season)) = 'spring' THEN 'Spring'
                    WHEN LOWER(TRIM(season)) = 'summer' THEN 'Summer'
                    WHEN LOWER(TRIM(season)) = 'fall' THEN 'Fall'
                    WHEN LOWER(TRIM(season)) = 'winter' THEN 'Winter'
                    WHEN LOWER(TRIM(season)) = 'all-season' THEN 'All-Season'
                    ELSE NULL
                END
            HAVING 
                CASE 
                    WHEN LOWER(TRIM(season)) = 'spring' THEN 'Spring'
                    WHEN LOWER(TRIM(season)) = 'summer' THEN 'Summer'
                    WHEN LOWER(TRIM(season)) = 'fall' THEN 'Fall'
                    WHEN LOWER(TRIM(season)) = 'winter' THEN 'Winter'
                    WHEN LOWER(TRIM(season)) = 'all-season' THEN 'All-Season'
                    ELSE NULL
                END IS NOT NULL
        ),
        all_seasons AS (
            SELECT season FROM (VALUES ('Spring'),('Summer'),('Fall'),('Winter'),('All-Season')) AS s(season)
        )
        SELECT 
            s.season AS name,
            ROUND(
                COALESCE(ibs.ingredient_dishes, 0) * 100.0 / NULLIF(sid.total_seasoned_dishes, 0), 
                2
            ) AS value,
            COALESCE(ibs.ingredient_dishes, 0) AS dish_count,
            sid.total_seasoned_dishes AS total_seasoned_dishes,
            tid.total_dishes AS total_dishes
        FROM all_seasons s
        LEFT JOIN ingredient_by_season ibs ON s.season = ibs.normalized_season
        CROSS JOIN seasoned_ingredient_dishes sid
        CROSS JOIN total_ingredient_dishes tid
        ORDER BY 
            CASE 
                WHEN s.season = 'Spring' THEN 1
                WHEN s.season = 'Summer' THEN 2
                WHEN s.season = 'Fall' THEN 3
                WHEN s.season = 'Winter' THEN 4
                WHEN s.season = 'All-Season' THEN 5
                ELSE 6
            END;
        """

        result = await execute_query(
            seasonal_query,
            options=QueryOptions(cacheable=True, ttl=600000)
        )

        if not result["rows"]:
            raise HTTPException(status_code=404, detail=f"No seasonal data found for ingredient: {ingredient}")

        # Parse distribution data
        distribution = []
        total_seasoned_dishes = 0
        total_dishes = 0
        
        print(f"Season distribution results: {result['rows']}")
        
        for row in result["rows"]:
            distribution.append(SeasonDistribution(
                name=str(row["name"]),
                value=float(row["value"] or 0.0)
            ))
            if row["total_seasoned_dishes"]:
                total_seasoned_dishes = int(row["total_seasoned_dishes"])
            if row["total_dishes"]:
                total_dishes = int(row["total_dishes"])

        # Calculate dishes without season data
        dishes_without_season_data = total_dishes - total_seasoned_dishes

        # Calculate analysis
        analysis = calculate_seasonal_analysis(distribution, total_seasoned_dishes, total_dishes, dishes_without_season_data)
        
        # Generate summary
        summary = generate_summary(ingredient, distribution, analysis)

        return SeasonResponse(
            ingredient=ingredient,
            distribution=distribution,
            analysis=analysis,
            summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch season distribution data")


def calculate_seasonal_analysis(distribution: List[SeasonDistribution], total_seasoned_dishes: int, total_dishes: int, dishes_without_season_data: int) -> SeasonAnalysis:
    """Calculate comprehensive seasonal analysis"""
    
    # Separate seasonal data from all-season
    seasonal_data = [item for item in distribution if item.name != 'All-Season']
    all_season_item = next((item for item in distribution if item.name == 'All-Season'), None)
    all_season_usage = all_season_item.value if all_season_item else 0.0
    
    if not seasonal_data:
        return SeasonAnalysis(
            peak_season="Unknown",
            peak_value=0.0,
            lowest_season="Unknown", 
            lowest_value=0.0,
            seasonal_variation=0.0,
            year_round_appeal=all_season_usage,
            seasonality_index="Low",
            is_seasonal_ingredient=False,
            all_season_usage=all_season_usage,
            total_dishes_analyzed=total_seasoned_dishes,
            dishes_with_season_data=total_seasoned_dishes,
            dishes_without_season_data=dishes_without_season_data
        )
    
    # Find peak and lowest seasons
    peak = max(seasonal_data, key=lambda x: x.value)
    lowest = min(seasonal_data, key=lambda x: x.value)
    
    # Calculate seasonal variation
    seasonal_variation = peak.value - lowest.value
    
    # Calculate average seasonal usage
    avg_seasonal = sum(item.value for item in seasonal_data) / len(seasonal_data)
    
    # Year-round appeal: weighted combination of seasonal consistency and all-season usage
    # Higher weight to all-season usage as it indicates true year-round versatility
    consistency_score = 100 - seasonal_variation  # Higher consistency = lower variation
    year_round_appeal = min(100, (consistency_score * 0.4 + all_season_usage * 0.6))
    
    # Determine seasonality index
    if seasonal_variation < 15:
        seasonality_index = "Low"
    elif seasonal_variation < 35:
        seasonality_index = "Moderate"
    else:
        seasonality_index = "High"
    
    # Determine if it's a seasonal ingredient
    # Consider both variation and peak concentration
    is_seasonal = seasonal_variation > 20 or peak.value > 35
    
    return SeasonAnalysis(
        peak_season=peak.name,
        peak_value=peak.value,
        lowest_season=lowest.name,
        lowest_value=lowest.value,
        seasonal_variation=seasonal_variation,
        year_round_appeal=year_round_appeal,
        seasonality_index=seasonality_index,
        is_seasonal_ingredient=is_seasonal,
        all_season_usage=all_season_usage,
        total_dishes_analyzed=total_seasoned_dishes,
        dishes_with_season_data=total_seasoned_dishes,
        dishes_without_season_data=dishes_without_season_data
    )


def generate_summary(ingredient: str, distribution: List[SeasonDistribution], analysis: SeasonAnalysis) -> str:
    """Generate a human-readable summary of seasonal patterns"""
    
    # Include information about missing season data
    data_coverage = f"Analysis based on {analysis.dishes_with_season_data} dishes with season data"
    if analysis.dishes_without_season_data > 0:
        total_dishes = analysis.dishes_with_season_data + analysis.dishes_without_season_data
        coverage_percent = (analysis.dishes_with_season_data / total_dishes) * 100
        data_coverage += f" ({coverage_percent:.1f}% of {total_dishes} total dishes)"
    
    if analysis.is_seasonal_ingredient:
        summary = f"{ingredient.title()} shows strong seasonal preferences, with peak usage in {analysis.peak_season} ({analysis.peak_value:.1f}% of seasoned dishes). "
        
        if analysis.seasonal_variation > 40:
            summary += f"The ingredient demonstrates high seasonal variation ({analysis.seasonal_variation:.1f}% difference between peak and low seasons), "
        else:
            summary += f"With moderate seasonal variation ({analysis.seasonal_variation:.1f}% range), "
            
        if analysis.all_season_usage > 20:
            summary += f"it also maintains significant year-round presence ({analysis.all_season_usage:.1f}% in all-season dishes). "
        else:
            summary += f"it shows limited all-season usage ({analysis.all_season_usage:.1f}%). "
            
    else:
        summary = f"{ingredient.title()} demonstrates consistent year-round usage with {analysis.seasonality_index.lower()} seasonal variation. "
        
        if analysis.all_season_usage > 30:
            summary += f"Strong all-season presence ({analysis.all_season_usage:.1f}%) indicates broad culinary versatility across menu types. "
        
        if analysis.peak_season and analysis.peak_value > 0:
            summary += f"While showing slight preference for {analysis.peak_season} ({analysis.peak_value:.1f}%), the ingredient maintains balanced usage across seasons. "
        else:
            summary += "The ingredient shows balanced usage across all seasons. "
    
    summary += data_coverage + "."
    
    return summary