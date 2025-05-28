# routers/applications_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional, Dict

class FlavorRoles(BaseModel):
    dominant: float
    enhancing: float
    background: float
    contrasting: float

class TopPairing(BaseModel):
    ingredient: str
    percentage: float

class ApplicationDetail(BaseModel):
    title: str
    share_percent: float
    growth: float
    lifecycle_phase: str  # emerging, growing, mature, declining
    appeal_score: float
    flavor_roles: FlavorRoles
    cuisine_distribution: Dict[str, float]
    top_pairings: List[TopPairing]
    top_dishes: List[str]

router = APIRouter()

@router.get("/applications/detailed", response_model=List[ApplicationDetail])
async def get_detailed_applications(
    ingredient: str = Query(..., description="Ingredient name"),
    category: Optional[str] = Query(None, description="Filter by general category"),
    lifecycle_phase: Optional[str] = Query(None, description="Filter by lifecycle phase"),
    min_share: Optional[float] = Query(None, description="Minimum share percentage")
):
    try:
        # Build filters
        category_filter = f"AND general_category ILIKE '%{category}%'" if category else ""
        
        applications_query = f"""
        WITH current_year_data AS (
            SELECT 
                specific_category,
                COUNT(DISTINCT dish_id) as current_dishes,
                COUNT(DISTINCT CASE WHEN ingredient_name ILIKE '%{ingredient}%' THEN dish_id END) as current_ingredient_dishes,
                AVG(CASE WHEN ingredient_name ILIKE '%{ingredient}%' THEN star_rating END) as avg_rating,
                SUM(CASE WHEN ingredient_name ILIKE '%{ingredient}%' THEN num_ratings ELSE 0 END) as total_ratings
            FROM ingredient_details
            WHERE specific_category IS NOT NULL 
                AND specific_category != ''
                AND year = 2024
                {category_filter}
            GROUP BY specific_category
        ),
        previous_year_data AS (
            SELECT 
                specific_category,
                COUNT(DISTINCT dish_id) as prev_dishes,
                COUNT(DISTINCT CASE WHEN ingredient_name ILIKE '%{ingredient}%' THEN dish_id END) as prev_ingredient_dishes
            FROM ingredient_details
            WHERE specific_category IS NOT NULL 
                AND specific_category != ''
                AND year = 2023
                {category_filter}
            GROUP BY specific_category
        ),
        all_data AS (
            SELECT 
                specific_category,
                COUNT(DISTINCT dish_id) as total_dishes,
                COUNT(DISTINCT CASE WHEN ingredient_name ILIKE '%{ingredient}%' THEN dish_id END) as total_ingredient_dishes,
                AVG(CASE WHEN ingredient_name ILIKE '%{ingredient}%' THEN star_rating END) as avg_rating,
                SUM(CASE WHEN ingredient_name ILIKE '%{ingredient}%' THEN num_ratings ELSE 0 END) as total_ratings
            FROM ingredient_details
            WHERE specific_category IS NOT NULL 
                AND specific_category != ''
                {category_filter}
            GROUP BY specific_category
        ),
        flavor_roles_data AS (
            SELECT 
                specific_category,
                COUNT(CASE WHEN flavor_role ILIKE '%dominant%' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as dominant_pct,
                COUNT(CASE WHEN flavor_role ILIKE '%enhancing%' OR flavor_role ILIKE '%supporting%' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as enhancing_pct,
                COUNT(CASE WHEN flavor_role ILIKE '%background%' OR flavor_role ILIKE '%base%' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as background_pct,
                COUNT(CASE WHEN flavor_role ILIKE '%contrast%' OR flavor_role ILIKE '%accent%' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as contrasting_pct
            FROM ingredient_details
            WHERE ingredient_name ILIKE '%{ingredient}%'
                AND specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
            GROUP BY specific_category
        ),
        total_ingredient_dishes AS (
            SELECT COUNT(DISTINCT dish_id) as total_count
            FROM ingredient_details
            WHERE ingredient_name ILIKE '%{ingredient}%'
                AND specific_category IS NOT NULL
                AND specific_category != ''
                {category_filter}
        )
        SELECT 
            ad.specific_category as title,
            ROUND(ad.total_ingredient_dishes * 100.0 / NULLIF(tid.total_count, 0), 2) as share_percent,
            ROUND(
                CASE 
                    WHEN pyd.prev_dishes = 0 OR pyd.prev_ingredient_dishes = 0 OR cyd.current_dishes = 0 THEN 0.0
                    ELSE ((cyd.current_ingredient_dishes * 100.0 / NULLIF(cyd.current_dishes, 0)) - 
                          (pyd.prev_ingredient_dishes * 100.0 / NULLIF(pyd.prev_dishes, 0)))
                END, 
                2
            ) as growth,
            ROUND(
                CASE 
                    WHEN ad.avg_rating IS NULL THEN 50.0
                    ELSE (ad.avg_rating / 5.0 * 80) + LEAST(ad.total_ratings / 100.0 * 20, 20)
                END, 
                1
            ) as appeal_score,
            COALESCE(frd.dominant_pct, 25.0) as dominant_pct,
            COALESCE(frd.enhancing_pct, 35.0) as enhancing_pct,
            COALESCE(frd.background_pct, 25.0) as background_pct,
            COALESCE(frd.contrasting_pct, 15.0) as contrasting_pct
        FROM all_data ad
        CROSS JOIN total_ingredient_dishes tid
        LEFT JOIN current_year_data cyd ON ad.specific_category = cyd.specific_category
        LEFT JOIN previous_year_data pyd ON ad.specific_category = pyd.specific_category
        LEFT JOIN flavor_roles_data frd ON ad.specific_category = frd.specific_category
        WHERE ad.total_ingredient_dishes > 0
        ORDER BY share_percent DESC
        LIMIT 20;
        """
        
        # Get cuisine distribution separately
        cuisine_query = f"""
        SELECT 
            specific_category,
            cuisine,
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY specific_category) as percentage
        FROM ingredient_details
        WHERE ingredient_name ILIKE '%{ingredient}%'
            AND specific_category IS NOT NULL
            AND specific_category != ''
            AND cuisine IS NOT NULL
            {category_filter}
        GROUP BY specific_category, cuisine
        ORDER BY specific_category, COUNT(*) DESC;
        """
        
        # Get top dishes separately
        dishes_query = f"""
        SELECT 
            specific_category,
            dish_name,
            ROW_NUMBER() OVER (PARTITION BY specific_category ORDER BY COALESCE(star_rating, 0) DESC, COALESCE(num_ratings, 0) DESC) as rank
        FROM ingredient_details
        WHERE ingredient_name ILIKE '%{ingredient}%'
            AND specific_category IS NOT NULL
            AND specific_category != ''
            AND dish_name IS NOT NULL
            AND dish_name != ''
            {category_filter}
        QUALIFY rank <= 4;
        """
        
        # Execute all queries
        main_result = await execute_query(
            applications_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        cuisine_result = await execute_query(
            cuisine_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        dishes_result = await execute_query(
            dishes_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if not main_result["rows"]:
            return []
        
        # Process cuisine data
        cuisine_by_category = {}
        if cuisine_result["rows"]:
            for row in cuisine_result["rows"]:
                category = row["specific_category"]
                if category not in cuisine_by_category:
                    cuisine_by_category[category] = {}
                cuisine_by_category[category][row["cuisine"]] = round(float(row["percentage"]), 1)
        
        # Process dishes data
        dishes_by_category = {}
        if dishes_result["rows"]:
            for row in dishes_result["rows"]:
                category = row["specific_category"]
                if category not in dishes_by_category:
                    dishes_by_category[category] = []
                dishes_by_category[category].append(row["dish_name"])
        
        # Build response
        applications = []
        for row in main_result["rows"]:
            title = str(row["title"])
            share_percent = float(row["share_percent"]) if row["share_percent"] is not None else 0.0
            growth = float(row["growth"]) if row["growth"] is not None else 0.0
            appeal_score = float(row["appeal_score"]) if row["appeal_score"] is not None else 50.0
            
            # Determine lifecycle phase
            if growth > 20:
                lifecycle_phase = "emerging"
            elif growth > 5:
                lifecycle_phase = "growing"
            elif growth < -10:
                lifecycle_phase = "declining"
            else:
                lifecycle_phase = "mature"
            
            # Build flavor roles
            flavor_roles = FlavorRoles(
                dominant=round(float(row["dominant_pct"]) if row["dominant_pct"] is not None else 25.0, 1),
                enhancing=round(float(row["enhancing_pct"]) if row["enhancing_pct"] is not None else 35.0, 1),
                background=round(float(row["background_pct"]) if row["background_pct"] is not None else 25.0, 1),
                contrasting=round(float(row["contrasting_pct"]) if row["contrasting_pct"] is not None else 15.0, 1)
            )
            
            # Get cuisine distribution (top 5)
            cuisine_dist = cuisine_by_category.get(title, {})
            top_cuisines = dict(sorted(cuisine_dist.items(), key=lambda x: x[1], reverse=True)[:5])
            
            # Get top dishes
            top_dishes = dishes_by_category.get(title, [])
            
            # Empty pairings for now
            top_pairings = []
            
            # Apply filters
            if lifecycle_phase and lifecycle_phase != lifecycle_phase:
                continue
            if min_share and share_percent < min_share:
                continue
            
            applications.append(ApplicationDetail(
                title=title,
                share_percent=share_percent,
                growth=growth,
                lifecycle_phase=lifecycle_phase,
                appeal_score=appeal_score,
                flavor_roles=flavor_roles,
                cuisine_distribution=top_cuisines,
                top_pairings=top_pairings,
                top_dishes=top_dishes
            ))
        
        return applications
        
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch applications data")