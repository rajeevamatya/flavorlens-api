# routers/trending_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List

import asyncio


class TopApplication(BaseModel):
    name: str
    count: int
    growth: float

class TopRecipe(BaseModel):
    dish: str
    avg_rating: float
    num_ratings: int
    source: str

class TrendingData(BaseModel):
    topApplications: List[TopApplication]
    topRecipes: List[TopRecipe]
    innovationOpportunities: List[str]


router = APIRouter()

@router.get("/trending-applications", response_model=TrendingData)
async def get_trending_applications(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        top_applications_query = f"""
        WITH category_counts AS (
            SELECT 
                specific_category AS name,
                COUNT(*) AS count
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND specific_category IS NOT NULL
            GROUP BY 
                specific_category
        ),
        total_count AS (
            SELECT 
                COUNT(*) AS total
            FROM 
                ingredient_details
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
                AND specific_category IS NOT NULL
        )
        SELECT 
            name,
            count,
            ROUND((count * 100.0 / NULLIF((SELECT total FROM total_count), 0)), 1) AS proportion
        FROM 
            category_counts
        ORDER BY 
            count DESC
        LIMIT 5;
        """
        
        top_recipes_query = f"""
        SELECT 
            dish_name AS dish,
            ROUND(CAST(star_rating AS DOUBLE), 1) AS avg_rating,
            num_ratings,
            source
        FROM 
            ingredient_details
        WHERE 
            ingredient_name ILIKE {ingredient_pattern}
            AND star_rating IS NOT NULL
            AND num_ratings > 0
        ORDER BY 
            star_rating DESC,
            num_ratings DESC
        LIMIT 10;
        """
        
        # Execute queries
        apps_result, recipes_result = await asyncio.gather(
            execute_query(top_applications_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(top_recipes_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        # Process top applications
        top_applications = []
        if apps_result["rows"]:
            for row in apps_result["rows"]:
                top_applications.append(TopApplication(
                    name=str(row["name"]),
                    count=int(row["count"]),
                    growth=float(row["proportion"]) if row["proportion"] is not None else 0.0  # Using proportion for the bar chart
                ))
        
        # Process top recipes
        top_recipes = []
        if recipes_result["rows"]:
            for row in recipes_result["rows"]:
                top_recipes.append(TopRecipe(
                    dish=str(row["dish"]),
                    avg_rating=float(row["avg_rating"]) if row["avg_rating"] is not None else 0.0,
                    num_ratings=int(row["num_ratings"]) if row["num_ratings"] is not None else 0,
                    source=str(row["source"]) if row["source"] is not None else "Unknown"
                ))
        
        # Generate innovation opportunities
        def generate_opportunities():
            base_opportunities = [
                f"{ingredient.capitalize()}-infused savory applications",
                f"Ready-to-use {ingredient} products",
                f"{ingredient.capitalize()} flavor innovation in snacks"
            ]
            
            if top_applications:
                categories = [app.name.split(' ')[-1] for app in top_applications if app.name]
                if any('ice' in cat.lower() or 'frozen' in cat.lower() for cat in categories):
                    base_opportunities.append(f"{ingredient.capitalize()}-flavored frozen novelties")
                if any('drink' in cat.lower() or 'beverage' in cat.lower() for cat in categories):
                    base_opportunities.append(f"Functional {ingredient} beverages with health benefits")
                if any('sauce' in cat.lower() or 'condiment' in cat.lower() for cat in categories):
                    base_opportunities.append(f"{ingredient.capitalize()}-based condiment innovations")
                if any('dessert' in cat.lower() or 'sweet' in cat.lower() for cat in categories):
                    base_opportunities.append(f"{ingredient.capitalize()}-enhanced premium desserts")
                if any('bread' in cat.lower() or 'baked' in cat.lower() for cat in categories):
                    base_opportunities.append(f"Artisanal {ingredient} baked goods")
            
            return base_opportunities[:4]
        
        innovation_opportunities = generate_opportunities()
        
        return TrendingData(
            topApplications=top_applications,
            topRecipes=top_recipes,
            innovationOpportunities=innovation_opportunities
        )
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trending applications data")