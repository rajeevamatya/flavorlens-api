# routers/texture_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Dict

class TextureAttribute(BaseModel):
    name: str
    proportion: float

class TextureTrend(BaseModel):
    year: int
    proportions: Dict[str, float]

class TextureData(BaseModel):
    texture_attributes: List[TextureAttribute]
    texture_trends: List[TextureTrend]

router = APIRouter()

@router.get("/texture-attributes", response_model=TextureData)
async def get_texture_attributes(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Get top 8 texture attributes by proportion
        texture_attribute_query = f"""
        WITH ingredient_dishes AS (
            SELECT COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
        ),
        texture_counts AS (
            SELECT 
                texture_attribute,
                COUNT(DISTINCT dish_id) AS dishes_with_texture
            FROM ingredient_texture
            WHERE ingredient_name ILIKE {ingredient_pattern}
            GROUP BY texture_attribute
        )
        SELECT 
            texture_attribute AS name,
            ROUND((dishes_with_texture * 100.0 / NULLIF(id.total_dishes, 0)), 2) AS proportion
        FROM texture_counts tc
        CROSS JOIN ingredient_dishes id
        ORDER BY proportion DESC
        LIMIT 8;
        """
        
        # Get proportions over time for top 8 textures
        texture_trends_query = f"""
        WITH top_textures AS (
            WITH ingredient_dishes AS (
                SELECT COUNT(DISTINCT dish_id) AS total_dishes
                FROM ingredient_details
                WHERE ingredient_name ILIKE {ingredient_pattern}
            ),
            texture_counts AS (
                SELECT 
                    texture_attribute,
                    COUNT(DISTINCT dish_id) AS dishes_with_texture
                FROM ingredient_texture
                WHERE ingredient_name ILIKE {ingredient_pattern}
                GROUP BY texture_attribute
            )
            SELECT texture_attribute
            FROM texture_counts tc
            CROSS JOIN ingredient_dishes id
            ORDER BY (dishes_with_texture * 100.0 / NULLIF(id.total_dishes, 0)) DESC
            LIMIT 8
        ),
        yearly_ingredient_dishes AS (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
            GROUP BY year
        ),
        yearly_texture AS (
            SELECT 
                year,
                texture_attribute,
                COUNT(DISTINCT dish_id) AS dishes_with_texture
            FROM ingredient_texture
            WHERE ingredient_name ILIKE {ingredient_pattern}
            AND texture_attribute IN (SELECT texture_attribute FROM top_textures)
            GROUP BY year, texture_attribute
        )
        SELECT 
            yt.year,
            yt.texture_attribute,
            ROUND((yt.dishes_with_texture * 100.0 / NULLIF(yid.total_dishes, 0)), 2) AS proportion
        FROM yearly_texture yt
        JOIN yearly_ingredient_dishes yid ON yt.year = yid.year
        ORDER BY yt.year, yt.texture_attribute;
        """
        
        # Execute queries
        attributes_result = await execute_query(
            texture_attribute_query, 
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        trends_result = await execute_query(
            texture_trends_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        # Process texture attributes
        texture_attributes = []
        if attributes_result["rows"]:
            for row in attributes_result["rows"]:
                texture_attributes.append(TextureAttribute(
                    name=row["name"],
                    proportion=float(row["proportion"])
                ))
        
        # Process trends data
        texture_trends = []
        if trends_result["rows"]:
            # Group by year
            year_data = {}
            for row in trends_result["rows"]:
                year = int(row["year"])
                texture = row["texture_attribute"]
                proportion = float(row["proportion"])
                
                if year not in year_data:
                    year_data[year] = {}
                year_data[year][texture] = proportion
            
            # Convert to list format
            for year in sorted(year_data.keys()):
                texture_trends.append(TextureTrend(
                    year=year,
                    proportions=year_data[year]
                ))
        
        return TextureData(
            texture_attributes=texture_attributes,
            texture_trends=texture_trends
        )
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch texture attributes data")