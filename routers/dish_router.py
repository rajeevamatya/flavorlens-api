# routers/dish_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional

class TopDish(BaseModel):
    name: str
    rating: Optional[float]
    reviews: Optional[int]

router = APIRouter()

@router.get("/dish/top-dishes", response_model=List[TopDish])
async def get_top_dishes(
    ingredient: str = Query(..., description="Ingredient name"),
    source: Optional[str] = Query(None, description="Filter by source: 'recipe', 'menu', or 'social'"),
    category: Optional[str] = Query(None, description="Filter by general category"),
    subcategory: Optional[str] = Query(None, description="Filter by specific category"),
    cuisine: Optional[str] = Query(None, description="Filter by cuisine"),
    country: Optional[str] = Query(None, description="Filter by country")
):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Build filters
        filters = []
        if source:
            if source not in ["recipe", "menu", "social"]:
                raise HTTPException(status_code=400, detail="Source must be 'recipe', 'menu', or 'social'")
            filters.append(f"source = '{source}'")
        
        if category:
            filters.append(f"general_category ILIKE '%{category}%'")
        
        if subcategory:
            filters.append(f"specific_category ILIKE '%{subcategory}%'")
        
        if cuisine:
            filters.append(f"cuisine ILIKE '%{cuisine}%'")
        
        if country:
            filters.append(f"country ILIKE '%{country}%'")
        
        # Combine all filters
        filter_clause = ""
        if filters:
            filter_clause = "AND " + " AND ".join(filters)
        
        top_dishes_query = f"""
        SELECT DISTINCT
            dish_name AS name,
            star_rating AS rating,
            num_ratings AS reviews
        FROM ingredient_details
        WHERE ingredient_name ILIKE {ingredient_pattern}
            AND dish_name IS NOT NULL
            AND dish_name != ''
            {filter_clause}
        ORDER BY 
            COALESCE(star_rating, 0) DESC,
            COALESCE(num_ratings, 0) DESC
        LIMIT 10;
        """

        result = await execute_query(
            top_dishes_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )

        if result["rows"]:
            dishes = []
            for row in result["rows"]:
                dishes.append(TopDish(
                    name=str(row["name"]),
                    rating=float(row["rating"]) if row["rating"] is not None else None,
                    reviews=int(row["reviews"]) if row["reviews"] is not None else None
                ))
            
            return dishes

        return []

    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch top dishes data")