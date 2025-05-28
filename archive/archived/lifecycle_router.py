# routers/lifecycle_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List

import asyncio

class SeasonalAdoption(BaseModel):
    seasons: List[str]
    values: List[float]
    peakSeason: str
    yearRoundAppeal: int
    seasonalityIndex: int
    seasonalNotes: str

class LifecycleData(BaseModel):
    years: List[int]
    mentions: List[int]
    currentStage: str
    marketPenetration: float
    growthProjection: float
    innovationPotential: str
    seasonalAdoption: SeasonalAdoption


router = APIRouter()

@router.get("/lifecycle-position", response_model=LifecycleData)
async def get_lifecycle_position(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Adoption phase query
        adoption_phase_query = f"""
        WITH ingredient_adoption AS (
            SELECT
                (COUNT(DISTINCT d.dish_id) * 100.0 / 
                  NULLIF((SELECT COUNT(DISTINCT dish_id) FROM flavorlens.main.dishes), 0)) AS penetration_percent,
                COUNT(DISTINCT d.dish_id) AS current_count,
                (COUNT(DISTINCT d.dish_id) - 
                  (SELECT COUNT(DISTINCT dishes.dish_id) 
                    FROM flavorlens.main.dishes 
                    JOIN flavorlens.main.dish_ingredients ON dishes.dish_id = dish_ingredients.dish_id 
                    WHERE dish_ingredients.name ILIKE {ingredient_pattern}
                    AND EXTRACT(YEAR FROM dishes.date_created) = 
                      GREATEST((SELECT MAX(EXTRACT(YEAR FROM date_created))-1 FROM flavorlens.main.dishes), 2020)))
                * 100.0 / 
                  NULLIF((SELECT COUNT(DISTINCT dishes.dish_id) 
                      FROM flavorlens.main.dishes 
                      JOIN flavorlens.main.dish_ingredients ON dishes.dish_id = dish_ingredients.dish_id 
                      WHERE dish_ingredients.name ILIKE {ingredient_pattern}
                      AND EXTRACT(YEAR FROM dishes.date_created) = 
                        GREATEST((SELECT MAX(EXTRACT(YEAR FROM date_created))-1 FROM flavorlens.main.dishes), 2020)), 1) 
                AS growth_percent
            FROM 
                flavorlens.main.dishes d
            JOIN 
                flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
            WHERE 
                di.name ILIKE {ingredient_pattern}
                AND EXTRACT(YEAR FROM d.date_created) = (SELECT GREATEST(MAX(EXTRACT(YEAR FROM date_created)), 2023) FROM flavorlens.main.dishes)
        )
        SELECT
            COALESCE(penetration_percent, 0) AS market_penetration,
            COALESCE(growth_percent, 0) AS growth_projection,
            CASE
                WHEN penetration_percent < 5 AND growth_percent > 50 THEN 'Inception'
                WHEN penetration_percent < 10 AND growth_percent > 30 THEN 'Early Adopters'
                WHEN penetration_percent BETWEEN 10 AND 25 AND growth_percent BETWEEN 15 AND 30 THEN 'Early Majority'
                WHEN penetration_percent BETWEEN 25 AND 50 AND growth_percent BETWEEN 5 AND 15 THEN 'Late Majority'
                WHEN (penetration_percent > 50 OR growth_percent < 5) THEN 'Mainstream'
                ELSE 'Early Adopters'
            END AS current_stage,
            CASE
                WHEN penetration_percent < 10 AND growth_percent > 40 THEN 'Very High'
                WHEN penetration_percent < 30 AND growth_percent > 20 THEN 'High'
                WHEN penetration_percent < 50 AND growth_percent > 10 THEN 'Moderate'
                WHEN penetration_percent > 50 OR growth_percent < 10 THEN 'Low'
                ELSE 'Moderate'
            END AS innovation_potential
        FROM
            ingredient_adoption;
        """
        
        # Historical trend query
        historical_trend_query = f"""
        WITH year_range AS (
            SELECT year 
            FROM (
                SELECT UNNEST(RANGE(2018, EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER + 1)) AS year
            )
        ),
        ingredient_yearly_counts AS (
            SELECT 
                EXTRACT(YEAR FROM d.date_created)::INTEGER AS year,
                COUNT(DISTINCT d.dish_id) AS ingredient_items
            FROM 
                flavorlens.main.dishes d
            JOIN 
                flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
            WHERE 
                di.name ILIKE {ingredient_pattern}
            GROUP BY 
                EXTRACT(YEAR FROM d.date_created)
        )
        SELECT 
            yr.year,
            COALESCE(iyc.ingredient_items, 0) AS mentions
        FROM 
            year_range yr
        LEFT JOIN 
            ingredient_yearly_counts iyc ON yr.year = iyc.year
        ORDER BY 
            yr.year;
        """
        
        # Seasonality query
        seasonality_query = f"""
        WITH seasonal_data AS (
            SELECT DISTINCT
                d.dish_id,
                COALESCE(d.season, 'All-Season') AS season
            FROM 
                flavorlens.main.dishes d
            JOIN 
                flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
            WHERE 
                di.name ILIKE {ingredient_pattern}
        ),
        all_seasons AS (
            SELECT season FROM (VALUES ('Spring'),('Summer'),('Fall'),('Winter'),('All-Season')) AS s(season)
        ),
        season_counts AS (
            SELECT 
                season,
                COUNT(*) AS dish_count,
                ROUND((COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM seasonal_data), 0)), 1) AS percentage
            FROM 
                seasonal_data
            GROUP BY 
                season
        )
        SELECT 
            s.season,
            COALESCE(sc.dish_count, 0) AS dish_count,
            COALESCE(sc.percentage, 0) AS percentage
        FROM 
            all_seasons s
        LEFT JOIN
            season_counts sc ON s.season = sc.season
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
        
        # Execute all queries
        phase_result, trend_result, seasonal_result = await asyncio.gather(
            execute_query(adoption_phase_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(historical_trend_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(seasonality_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        if phase_result["rows"]:
            # Process the results
            years = [int(row["year"]) for row in trend_result["rows"]]
            mentions = [int(row["mentions"]) for row in trend_result["rows"]]
            
            # Calculate seasonal distribution
            seasons = [row["season"] for row in seasonal_result["rows"]]
            values = [float(row["percentage"]) for row in seasonal_result["rows"]]
            
            # Find peak season
            peak_season = 'All-Season'
            max_value = 0
            for row in seasonal_result["rows"]:
                if float(row["percentage"]) > max_value and row["season"] != 'All-Season':
                    max_value = float(row["percentage"])
                    peak_season = row["season"]
            
            # Calculate year-round appeal
            all_season_percentage = 0
            for row in seasonal_result["rows"]:
                if row["season"] == 'All-Season':
                    all_season_percentage = float(row["percentage"])
                    break
            
            max_seasonal = max([float(row["percentage"]) for row in seasonal_result["rows"]])
            year_round_appeal = round(all_season_percentage + (100 - max_seasonal))
            seasonality_index = round(100 - year_round_appeal)
            
            seasonal_notes = f"{'Consistent year-round usage' if peak_season == 'All-Season' else f'Strongest in {peak_season}'} with {year_round_appeal}% year-round appeal"
            
            phase_row = phase_result["rows"][0]
            
            return LifecycleData(
                years=years,
                mentions=mentions,
                currentStage=phase_row["current_stage"],
                marketPenetration=float(phase_row["market_penetration"]),
                growthProjection=float(phase_row["growth_projection"]),
                innovationPotential=phase_row["innovation_potential"],
                seasonalAdoption=SeasonalAdoption(
                    seasons=seasons,
                    values=values,
                    peakSeason=peak_season,
                    yearRoundAppeal=year_round_appeal,
                    seasonalityIndex=seasonality_index,
                    seasonalNotes=seasonal_notes
                )
            )
        
        # Return empty data structure if no results
        return LifecycleData(
            years=[],
            mentions=[],
            currentStage='Unknown',
            marketPenetration=0.0,
            growthProjection=0.0,
            innovationPotential='Unknown',
            seasonalAdoption=SeasonalAdoption(
                seasons=[],
                values=[],
                peakSeason='',
                yearRoundAppeal=0,
                seasonalityIndex=0,
                seasonalNotes=''
            )
        )
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch lifecycle data from database")