# routers/pairings_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional

class TopApplication(BaseModel):
    application: str
    percentage: int

class TopFlavor(BaseModel):
    flavor: str
    percentage: int

class PairingData(BaseModel):
    title: str
    share_percent: float
    growth: float
    lifecycle_phase: str
    appeal_score: int
    dominant_ingredient_percent: int
    partner_ingredient_percent: int
    partner_name: str
    top_applications: List[TopApplication]
    top_flavors: List[TopFlavor]
    top_dishes: List[str]

class PairingsResponse(BaseModel):
    ingredient: str
    pairings: List[PairingData]
    total_pairings: int

router = APIRouter()

@router.get("/pairings", response_model=PairingsResponse)
async def get_ingredient_pairings(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Main pairings query using ingredient_details directly
        pairings_query = f"""
        WITH base_ingredient_data AS (
            -- Get all dishes for the target ingredient to calculate total base
            SELECT DISTINCT dish_id
            FROM ingredient_details 
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND ingredient_role = 'flavor-aromatic'
        ),
        ingredient_pairs AS (
            -- Get all ingredient pairings for the target ingredient
            SELECT 
                i1.ingredient_name AS base_ingredient,
                i2.ingredient_name AS paired_ingredient,
                i1.dish_id,
                i1.dish_name,
                i1.general_category,
                i1.year,
                i1.star_rating,
                i1.flavor_role AS base_flavor_role,
                i2.flavor_role AS paired_flavor_role
            FROM ingredient_details i1
            JOIN ingredient_details i2 ON i1.dish_id = i2.dish_id
            WHERE i1.ingredient_name ILIKE {ingredient_pattern}
                AND i1.ingredient_role = 'flavor-aromatic'
                AND i2.ingredient_name NOT ILIKE {ingredient_pattern}
                AND i2.ingredient_role = 'flavor-aromatic'
                AND i1.ingredient_id != i2.ingredient_id
        ),
        pairing_metrics AS (
            SELECT 
                paired_ingredient,
                COUNT(DISTINCT dish_id) AS unique_dishes,
                
                -- Calculate share percentage
                ROUND(COUNT(DISTINCT dish_id) * 100.0 / 
                    (SELECT COUNT(*) FROM base_ingredient_data), 1) AS share_percentage,
                
                -- Growth calculation (2023 vs 2024)
                COUNT(CASE WHEN year = 2024 THEN 1 END) AS count_2024,
                COUNT(CASE WHEN year = 2023 THEN 1 END) AS count_2023,
                
                -- Appeal score
                ROUND(AVG(star_rating) * 20, 0) AS appeal_score,
                AVG(star_rating) AS avg_rating,
                
                -- Flavor balance calculations
                COUNT(CASE WHEN base_flavor_role = 'dominant' THEN 1 END) AS base_dominant_count,
                COUNT(CASE WHEN paired_flavor_role = 'dominant' THEN 1 END) AS paired_dominant_count
                
            FROM ingredient_pairs
            GROUP BY paired_ingredient
        ),
        category_stats AS (
            SELECT 
                paired_ingredient,
                general_category,
                COUNT(DISTINCT dish_id) AS category_dishes
            FROM ingredient_pairs
            GROUP BY paired_ingredient, general_category
        ),
        application_breakdown AS (
            SELECT 
                cs.paired_ingredient,
                STRING_AGG(
                    cs.general_category || '|' || 
                    ROUND(cs.category_dishes * 100.0 / pm.unique_dishes, 0), 
                    ',' 
                    ORDER BY cs.category_dishes DESC
                ) AS applications_data
            FROM category_stats cs
            JOIN pairing_metrics pm ON cs.paired_ingredient = pm.paired_ingredient
            GROUP BY cs.paired_ingredient
        ),
        top_dishes_agg AS (
            SELECT 
                paired_ingredient,
                STRING_AGG(dish_name, ',' ORDER BY star_rating DESC) AS top_dishes_data
            FROM (
                SELECT 
                    paired_ingredient,
                    dish_name,
                    star_rating,
                    ROW_NUMBER() OVER (PARTITION BY paired_ingredient ORDER BY star_rating DESC, dish_name) as rn
                FROM ingredient_pairs
                GROUP BY paired_ingredient, dish_name, star_rating
            ) ranked_dishes
            WHERE rn <= 4
            GROUP BY paired_ingredient
        )
        SELECT 
            pm.paired_ingredient,
            pm.share_percentage,
            CASE 
                WHEN pm.count_2023 = 0 AND pm.count_2024 > 0 THEN 100.0
                WHEN pm.count_2023 = 0 THEN 0.0
                ELSE ROUND((pm.count_2024 - pm.count_2023) * 100.0 / pm.count_2023, 1)
            END AS growth_rate,
            CASE 
                WHEN pm.count_2024 > pm.count_2023 * 1.2 THEN 'growing'
                WHEN pm.unique_dishes > 15 AND pm.avg_rating > 4.0 THEN 'mature'
                WHEN pm.unique_dishes > 8 THEN 'mature'
                ELSE 'emerging'
            END AS lifecycle_phase,
            pm.appeal_score,
            ROUND(pm.base_dominant_count * 100.0 / pm.unique_dishes, 0) AS base_dominant_percent,
            ROUND(pm.paired_dominant_count * 100.0 / pm.unique_dishes, 0) AS paired_dominant_percent,
            COALESCE(ab.applications_data, '') AS applications_data,
            COALESCE(td.top_dishes_data, '') AS top_dishes_data,
            pm.unique_dishes
        FROM pairing_metrics pm
        LEFT JOIN application_breakdown ab ON pm.paired_ingredient = ab.paired_ingredient
        LEFT JOIN top_dishes_agg td ON pm.paired_ingredient = td.paired_ingredient
        WHERE pm.unique_dishes >= 3
        ORDER BY pm.share_percentage DESC
        LIMIT 20;
        """
        
        result = await execute_query(
            pairings_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if not result["rows"]:
            raise HTTPException(status_code=404, detail=f"No pairings found for ingredient: {ingredient}")
        
        pairings = []
        for row in result["rows"]:
            try:
                # Debug: Print the row data to see what we're getting
                print(f"Processing row: {row}")
                
                # Parse applications data
                applications = []
                if row["applications_data"]:
                    app_items = row["applications_data"].split(',')
                    for app_item in app_items[:4]:  # Top 4 applications
                        if '|' in app_item:
                            app_name, app_percent = app_item.split('|')
                            applications.append(TopApplication(
                                application=app_name.strip(),
                                percentage=int(float(app_percent))  # Convert float string to int
                            ))
                
                # Generate flavor data (simplified for now - you can enhance this)
                flavors = generate_flavor_data(row["paired_ingredient"])
                
                # Parse top dishes
                dishes = []
                if row["top_dishes_data"]:
                    dishes = [dish.strip() for dish in row["top_dishes_data"].split(',')[:4]]
                
                # Create pairing title
                paired_name = row["paired_ingredient"].strip()
                title = f"{ingredient.title()} + {paired_name.title()}"
                
                pairings.append(PairingData(
                    title=title,
                    share_percent=float(row["share_percentage"]),
                    growth=float(row["growth_rate"]),
                    lifecycle_phase=str(row["lifecycle_phase"]),
                    appeal_score=int(float(row["appeal_score"])),  # Convert float string to int
                    dominant_ingredient_percent=int(float(row["base_dominant_percent"])),  # Convert float string to int
                    partner_ingredient_percent=int(float(row["paired_dominant_percent"])),  # Convert float string to int
                    partner_name=paired_name.title(),
                    top_applications=applications,
                    top_flavors=flavors,
                    top_dishes=dishes
                ))
                
            except Exception as e:
                print(f"Error processing row {row}: {e}")
                continue
        
        return PairingsResponse(
            ingredient=ingredient.title(),
            pairings=pairings,
            total_pairings=len(pairings)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch pairings data")


def generate_flavor_data(paired_ingredient: str) -> List[TopFlavor]:
    """Generate flavor data based on ingredient name (simplified approach)"""
    
    flavors_map = {
        'white chocolate': [
            TopFlavor(flavor="Sweet", percentage=38),
            TopFlavor(flavor="Creamy", percentage=32),
            TopFlavor(flavor="Rich", percentage=18),
            TopFlavor(flavor="Smooth", percentage=12)
        ],
        'vanilla': [
            TopFlavor(flavor="Sweet", percentage=42),
            TopFlavor(flavor="Smooth", percentage=28),
            TopFlavor(flavor="Floral", percentage=20),
            TopFlavor(flavor="Warm", percentage=10)
        ],
        'coconut': [
            TopFlavor(flavor="Tropical", percentage=35),
            TopFlavor(flavor="Creamy", percentage=30),
            TopFlavor(flavor="Nutty", percentage=20),
            TopFlavor(flavor="Refreshing", percentage=15)
        ],
        'strawberry': [
            TopFlavor(flavor="Sweet", percentage=40),
            TopFlavor(flavor="Fruity", percentage=32),
            TopFlavor(flavor="Fresh", percentage=18),
            TopFlavor(flavor="Tart", percentage=10)
        ],
        'honey': [
            TopFlavor(flavor="Sweet", percentage=45),
            TopFlavor(flavor="Floral", percentage=25),
            TopFlavor(flavor="Complex", percentage=20),
            TopFlavor(flavor="Natural", percentage=10)
        ],
        'lemon': [
            TopFlavor(flavor="Citrusy", percentage=38),
            TopFlavor(flavor="Tangy", percentage=28),
            TopFlavor(flavor="Refreshing", percentage=22),
            TopFlavor(flavor="Bright", percentage=12)
        ],
        'sea salt': [
            TopFlavor(flavor="Salty", percentage=35),
            TopFlavor(flavor="Umami", percentage=30),
            TopFlavor(flavor="Complex", percentage=20),
            TopFlavor(flavor="Mineral", percentage=15)
        ],
        'mango': [
            TopFlavor(flavor="Tropical", percentage=42),
            TopFlavor(flavor="Sweet", percentage=30),
            TopFlavor(flavor="Fruity", percentage=18),
            TopFlavor(flavor="Exotic", percentage=10)
        ]
    }
    
    # Default flavors if ingredient not in map
    default_flavors = [
        TopFlavor(flavor="Sweet", percentage=30),
        TopFlavor(flavor="Complex", percentage=25),
        TopFlavor(flavor="Balanced", percentage=25),
        TopFlavor(flavor="Unique", percentage=20)
    ]
    
    ingredient_lower = paired_ingredient.lower().strip()
    
    # Find matching flavor profile
    for key, flavors in flavors_map.items():
        if key in ingredient_lower:
            return flavors
    
    return default_flavors