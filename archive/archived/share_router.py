# routers/share_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel

class ShareData(BaseModel):
    share_percent: float
    change_percent: float

router = APIRouter()

@router.get("/recipe-share", response_model=ShareData)
async def get_recipe_share(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"

        recipe_share_query = f"""
        SELECT 
            -- Overall share
            COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} THEN dish_id END) * 100.0 / 
            NULLIF(COUNT(DISTINCT dish_id), 0) AS share_percent,
            
            -- Change in percentage points
            (COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} AND year = 2023 THEN dish_id END) * 100.0 / 
             NULLIF(COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END), 0)) - 
            (COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} AND year = 2022 THEN dish_id END) * 100.0 / 
             NULLIF(COUNT(DISTINCT CASE WHEN year = 2022 THEN dish_id END), 0)) AS change_percent

        FROM ingredient_details
        WHERE source = 'recipe';
        """

        result = await execute_query(
            recipe_share_query,
            options=QueryOptions(cacheable=True, ttl=600000)
        )

        if result["rows"]:
            row = result["rows"][0]
            return ShareData(
                share_percent=round(float(row["share_percent"] or 0.0), 2),
                change_percent=round(float(row["change_percent"] or 0.0), 2)
            )

        return ShareData(share_percent=0.0, change_percent=0.0)

    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/menu-share", response_model=ShareData)
async def get_menu_share(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"

        menu_share_query = f"""
        SELECT 
            -- Overall share
            COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} THEN dish_id END) * 100.0 / 
            NULLIF(COUNT(DISTINCT dish_id), 0) AS share_percent,
            
            -- Change in percentage points
            (COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} AND year = 2023 THEN dish_id END) * 100.0 / 
             NULLIF(COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END), 0)) - 
            (COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} AND year = 2022 THEN dish_id END) * 100.0 / 
             NULLIF(COUNT(DISTINCT CASE WHEN year = 2022 THEN dish_id END), 0)) AS change_percent

        FROM ingredient_details
        WHERE source = 'menu';
        """

        result = await execute_query(
            menu_share_query,
            options=QueryOptions(cacheable=True, ttl=600000)
        )

        if result["rows"]:
            row = result["rows"][0]
            return ShareData(
                share_percent=round(float(row["share_percent"] or 0.0), 2),
                change_percent=round(float(row["change_percent"] or 0.0), 2)
            )

        return ShareData(share_percent=0.0, change_percent=0.0)

    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/social-share", response_model=ShareData)
async def get_social_share(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"

        social_share_query = f"""
        SELECT 
            -- Overall share
            COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} THEN dish_id END) * 100.0 / 
            NULLIF(COUNT(DISTINCT dish_id), 0) AS share_percent,
            
            -- Change in percentage points
            (COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} AND year = 2023 THEN dish_id END) * 100.0 / 
             NULLIF(COUNT(DISTINCT CASE WHEN year = 2023 THEN dish_id END), 0)) - 
            (COUNT(DISTINCT CASE WHEN ingredient_name ILIKE {ingredient_pattern} AND year = 2022 THEN dish_id END) * 100.0 / 
             NULLIF(COUNT(DISTINCT CASE WHEN year = 2022 THEN dish_id END), 0)) AS change_percent

        FROM ingredient_details
        WHERE source = 'social';
        """

        result = await execute_query(
            social_share_query,
            options=QueryOptions(cacheable=True, ttl=600000)
        )

        if result["rows"]:
            row = result["rows"][0]
            return ShareData(
                share_percent=round(float(row["share_percent"] or 0.0), 2),
                change_percent=round(float(row["change_percent"] or 0.0), 2)
            )

        return ShareData(share_percent=0.0, change_percent=0.0)

    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")