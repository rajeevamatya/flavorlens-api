# routers/texture_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import TextureData, TextureAttribute, TextureTrend
from typing import List

router = APIRouter()

@router.get("/texture-attributes", response_model=TextureData)
async def get_texture_attributes(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # SQL query for texture attributes data
        texture_attribute_query = f"""
        WITH texture_mentions AS (
            SELECT 
                texture_attribute,
                COUNT(*) AS mention_count,
                AVG(CAST(star_rating AS FLOAT)) AS avg_rating,
                SUM(num_ratings) AS total_ratings
            FROM 
                flavorlens.main.ingredient_texture
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
            GROUP BY 
                texture_attribute
        ),
        total_mentions AS (
            SELECT SUM(mention_count) AS total FROM texture_mentions
        )
        SELECT 
            texture_attribute AS name,
            mention_count AS count,
            ROUND((mention_count * 100.0 / (SELECT total FROM total_mentions)), 1) AS value,
            avg_rating,
            total_ratings
        FROM 
            texture_mentions
        ORDER BY 
            value DESC
        LIMIT 12;
        """
        
        # SQL query for texture trends over time
        texture_trends_query = f"""
        WITH yearly_texture AS (
            SELECT 
                "year",
                texture_attribute,
                COUNT(*) AS yearly_count,
                ROW_NUMBER() OVER (PARTITION BY "year" ORDER BY COUNT(*) DESC) as rank
            FROM 
                flavorlens.main.ingredient_texture
            WHERE 
                ingredient_name ILIKE {ingredient_pattern}
            GROUP BY 
                "year", texture_attribute
        ),
        texture_years AS (
            SELECT DISTINCT "year" FROM flavorlens.main.ingredient_texture
            WHERE "year" >= 2019 AND "year" <= 2024
            ORDER BY "year"
        )
        SELECT 
            ty."year",
            MAX(CASE WHEN yt.texture_attribute = 'Creamy' THEN COALESCE(yt.yearly_count, 0) ELSE 0 END) AS creamy,
            MAX(CASE WHEN yt.texture_attribute = 'Smooth' THEN COALESCE(yt.yearly_count, 0) ELSE 0 END) AS smooth,
            MAX(CASE WHEN yt.texture_attribute = 'Thick' THEN COALESCE(yt.yearly_count, 0) ELSE 0 END) AS thick,
            MAX(CASE WHEN yt.texture_attribute = 'Frothy' THEN COALESCE(yt.yearly_count, 0) ELSE 0 END) AS frothy,
            MAX(CASE WHEN yt.texture_attribute = 'Powdery' THEN COALESCE(yt.yearly_count, 0) ELSE 0 END) AS powdery
        FROM 
            texture_years ty
        LEFT JOIN 
            yearly_texture yt ON ty."year" = yt."year"
        GROUP BY 
            ty."year"
        ORDER BY 
            ty."year";
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
        
        # Define texture scale descriptions
        texture_scales = {
            "Creamy": ["Watery", "Creamy"],
            "Smooth": ["Rough", "Smooth"],
            "Thick": ["Thin", "Thick"],
            "Frothy": ["Flat", "Frothy"],
            "Powdery": ["Solid", "Powdery"],
            "Velvety": ["Rough", "Velvety"],
            "Sticky": ["Non-sticky", "Sticky"],
            "Silky": ["Coarse", "Silky"],
            "Grainy": ["Fine", "Grainy"],
            "Fluffy": ["Dense", "Fluffy"],
            "Crunchy": ["Soft", "Crunchy"],
            "Chewy": ["Tender", "Chewy"]
        }
        
        color_palette = [
            "#00255a", "#199ef3", "#10B981", "#F59E0B", "#8B5CF6", 
            "#EF4444", "#3179c0", "#5590d6", "#84abdd", "#adc5e5", 
            "#c3d5ec", "#d1e3f6"
        ]
        
        # Process texture attributes
        texture_attributes = []
        if attributes_result["rows"]:
            for index, row in enumerate(attributes_result["rows"]):
                texture_attributes.append(TextureAttribute(
                    name=row["name"],
                    value=float(row["value"]),
                    count=int(row["count"]),
                    avg_rating=float(row["avg_rating"]) if row["avg_rating"] else 0.0,
                    total_ratings=int(row["total_ratings"]) if row["total_ratings"] else 0,
                    scale=texture_scales.get(row["name"], ["Low", "High"]),
                    fill=color_palette[index % len(color_palette)]
                ))
        
        # Process trends data
        processed_trends = []
        if trends_result["rows"]:
            for row in trends_result["rows"]:
                processed_trends.append(TextureTrend(
                    year=str(row["year"]),
                    creamy=int(row["creamy"]) if row["creamy"] else 0,
                    smooth=int(row["smooth"]) if row["smooth"] else 0,
                    thick=int(row["thick"]) if row["thick"] else 0,
                    frothy=int(row["frothy"]) if row["frothy"] else 0,
                    powdery=int(row["powdery"]) if row["powdery"] else 0
                ))
        
        return TextureData(
            textureAttributesData=texture_attributes,
            textureAttributeTrendData=processed_trends
        )
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch texture attributes data")

