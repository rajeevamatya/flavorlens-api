from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
from config import CURRENT_YEAR
import math

router = APIRouter()

class TopApplication(BaseModel):
    application: str
    percentage: float

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
    top_dishes: List[str]
    general_categories: List[str]

class PaginationInfo(BaseModel):
    current_page: int
    total_pages: int
    total_items: int
    items_per_page: int
    has_next: bool
    has_previous: bool

class PairingsResponse(BaseModel):
    ingredient: str
    pairings: List[PairingData]
    total_pairings: int
    pagination: PaginationInfo

@router.get("/pairings", response_model=PairingsResponse)
async def get_ingredient_pairings(
    ingredient: str = Query(..., description="Ingredient name"),
    category: str = Query(None, description="General category filter (optional)"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(25, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: str = Query("share_percent", description="Sort column: share_percent, growth, appeal_score, dominant_ingredient_percent, title"),
    sort_direction: str = Query("desc", description="Sort direction: asc or desc"),
    lifecycle_phase: str = Query(None, description="Lifecycle phase filter: emerging, growing, mature, declining"),
    search: str = Query(None, description="Search in pairing titles")
):
    try:
        previous_year = CURRENT_YEAR - 1
        
        # Build the base WHERE conditions
        base_where = f"base_ingredient ILIKE '%{ingredient}%'"
        pairing_where = f"base_ingredient ILIKE '%{ingredient}%' AND paired_flavor_role != 'background' AND LOWER(base_ingredient) != LOWER(paired_ingredient)"        
        # Category filter
        if category and category.lower() != "all categories":
            safe_category = category.replace("'", "''")
            category_condition = f"AND general_category = '{safe_category}'"
            base_where = base_where + " " + category_condition
            pairing_where = pairing_where + " " + category_condition
            print(f"Applying category filter: {category}")
        else:
            print("No category filter applied")
        
        # Build additional filters for the final WHERE clause
        additional_filters = []
        
        if lifecycle_phase and lifecycle_phase.lower() != "all":
            safe_phase = lifecycle_phase.replace("'", "''")
            additional_filters.append(f"gc.lifecycle_phase = '{safe_phase}'")
            
        if search:
            safe_search = search.replace("'", "''")
            additional_filters.append(f"gc.paired_ingredient ILIKE '%{safe_search}%'")
        
        # Build the sorting clause
        sort_mapping = {
            "share_percent": "gc.share_percentage",
            "growth": "gc.growth_rate", 
            "appeal_score": "gc.appeal_score",
            "dominant_ingredient_percent": "base_dominant_percent",
            "title": "gc.paired_ingredient"
        }
        
        sort_column = sort_mapping.get(sort_by, "gc.share_percentage")
        sort_dir = "ASC" if sort_direction.lower() == "asc" else "DESC"
        
        # Calculate offset for pagination
        offset = (page - 1) * limit
        
        # First, get the total count with filters applied
        count_query = f"""
        WITH base_ingredient_data AS (
            SELECT COUNT(DISTINCT dish_id) as total_base_dishes
            FROM ingredient_pairings 
            WHERE {base_where}
        ),
        base_ingredient_by_year AS (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) as base_dishes_by_year
            FROM ingredient_pairings 
            WHERE {base_where}
            GROUP BY year
        ),
        yearly_pairing_data AS (
            SELECT 
                paired_ingredient,
                year,
                COUNT(DISTINCT dish_id) AS yearly_dishes,
                ROUND(
                    COUNT(DISTINCT dish_id) * 100.0 / 
                    NULLIF((
                        SELECT base_dishes_by_year 
                        FROM base_ingredient_by_year biy 
                        WHERE biy.year = ip.year
                    ), 0), 
                    2
                ) AS yearly_penetration
            FROM ingredient_pairings ip
            WHERE {pairing_where}
                AND year IN ({previous_year}, {CURRENT_YEAR})
            GROUP BY paired_ingredient, year
        ),
        pairing_metrics AS (
            SELECT 
                paired_ingredient,
                COUNT(DISTINCT dish_id) AS unique_dishes,
                CASE 
                    WHEN (SELECT total_base_dishes FROM base_ingredient_data) = 0 THEN 0.0
                    ELSE ROUND(COUNT(DISTINCT dish_id) * 100.0 / 
                        (SELECT total_base_dishes FROM base_ingredient_data), 1)
                END AS share_percentage,
                ROUND(AVG(star_rating) * 20, 0) AS appeal_score,
                AVG(star_rating) AS avg_rating,
                COUNT(DISTINCT CASE WHEN base_flavor_role = 'dominant' THEN dish_id END) AS base_dominant_count,
                COUNT(DISTINCT CASE WHEN paired_flavor_role = 'dominant' THEN dish_id END) AS paired_dominant_count
            FROM ingredient_pairings
            WHERE {pairing_where}
            GROUP BY paired_ingredient
        ),
        growth_calculation AS (
            SELECT 
                pm.paired_ingredient,
                pm.unique_dishes,
                pm.share_percentage,
                pm.appeal_score,
                pm.avg_rating,
                pm.base_dominant_count,
                pm.paired_dominant_count,
                CASE 
                    WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                        CASE 
                            WHEN curr_year.yearly_penetration > 0 THEN 100.0
                            ELSE 0.0
                        END
                    ELSE 
                        ROUND(
                            ((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 
                            1
                        )
                END AS growth_rate,
                CASE 
                    WHEN pm.share_percentage < 5 AND (
                        CASE 
                            WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                                CASE WHEN curr_year.yearly_penetration > 0 THEN 100.0 ELSE 0.0 END
                            ELSE 
                                ROUND(((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 1)
                        END
                    ) > 15 THEN 'emerging'
                    WHEN pm.share_percentage BETWEEN 5 AND 25 AND (
                        CASE 
                            WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                                CASE WHEN curr_year.yearly_penetration > 0 THEN 100.0 ELSE 0.0 END
                            ELSE 
                                ROUND(((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 1)
                        END
                    ) > 5 THEN 'growing'
                    WHEN pm.share_percentage >= 25 AND (
                        CASE 
                            WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                                CASE WHEN curr_year.yearly_penetration > 0 THEN 100.0 ELSE 0.0 END
                            ELSE 
                                ROUND(((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 1)
                        END
                    ) < -5 THEN 'declining'
                    ELSE 'mature'
                END AS lifecycle_phase,
                CASE 
                    WHEN pm.unique_dishes = 0 THEN 0
                    ELSE ROUND(pm.base_dominant_count * 100.0 / pm.unique_dishes, 0)
                END AS base_dominant_percent,
                CASE 
                    WHEN pm.unique_dishes = 0 THEN 0
                    ELSE ROUND(pm.paired_dominant_count * 100.0 / pm.unique_dishes, 0)
                END AS paired_dominant_percent
            FROM pairing_metrics pm
            LEFT JOIN yearly_pairing_data prev_year ON pm.paired_ingredient = prev_year.paired_ingredient AND prev_year.year = {previous_year}
            LEFT JOIN yearly_pairing_data curr_year ON pm.paired_ingredient = curr_year.paired_ingredient AND curr_year.year = {CURRENT_YEAR}
        )
        SELECT COUNT(*) as total_count
        FROM growth_calculation gc
        WHERE gc.unique_dishes >= 3
        """
        
        # Add additional filters to count query
        if additional_filters:
            count_query += " AND " + " AND ".join(additional_filters)
        
        count_result = await execute_query(count_query)
        total_items = count_result["rows"][0]["total_count"] if count_result["rows"] else 0
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
        
        # Now get the paginated data
        main_query = f"""
        WITH base_ingredient_data AS (
            SELECT COUNT(DISTINCT dish_id) as total_base_dishes
            FROM ingredient_pairings 
            WHERE {base_where}
        ),
        base_ingredient_by_year AS (
            SELECT 
                year,
                COUNT(DISTINCT dish_id) as base_dishes_by_year
            FROM ingredient_pairings 
            WHERE {base_where}
            GROUP BY year
        ),
        yearly_pairing_data AS (
            SELECT 
                paired_ingredient,
                year,
                COUNT(DISTINCT dish_id) AS yearly_dishes,
                ROUND(
                    COUNT(DISTINCT dish_id) * 100.0 / 
                    NULLIF((
                        SELECT base_dishes_by_year 
                        FROM base_ingredient_by_year biy 
                        WHERE biy.year = ip.year
                    ), 0), 
                    2
                ) AS yearly_penetration
            FROM ingredient_pairings ip
            WHERE {pairing_where}
                AND year IN ({previous_year}, {CURRENT_YEAR})
            GROUP BY paired_ingredient, year
        ),
        pairing_metrics AS (
            SELECT 
                paired_ingredient,
                COUNT(DISTINCT dish_id) AS unique_dishes,
                CASE 
                    WHEN (SELECT total_base_dishes FROM base_ingredient_data) = 0 THEN 0.0
                    ELSE ROUND(COUNT(DISTINCT dish_id) * 100.0 / 
                        (SELECT total_base_dishes FROM base_ingredient_data), 1)
                END AS share_percentage,
                ROUND(AVG(star_rating) * 20, 0) AS appeal_score,
                AVG(star_rating) AS avg_rating,
                COUNT(DISTINCT CASE WHEN base_flavor_role = 'dominant' THEN dish_id END) AS base_dominant_count,
                COUNT(DISTINCT CASE WHEN paired_flavor_role = 'dominant' THEN dish_id END) AS paired_dominant_count
            FROM ingredient_pairings
            WHERE {pairing_where}
            GROUP BY paired_ingredient
        ),
        growth_calculation AS (
            SELECT 
                pm.paired_ingredient,
                pm.unique_dishes,
                pm.share_percentage,
                pm.appeal_score,
                pm.avg_rating,
                pm.base_dominant_count,
                pm.paired_dominant_count,
                CASE 
                    WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                        CASE 
                            WHEN curr_year.yearly_penetration > 0 THEN 100.0
                            ELSE 0.0
                        END
                    ELSE 
                        ROUND(
                            ((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 
                            1
                        )
                END AS growth_rate,
                CASE 
                    WHEN pm.share_percentage < 5 AND (
                        CASE 
                            WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                                CASE WHEN curr_year.yearly_penetration > 0 THEN 100.0 ELSE 0.0 END
                            ELSE 
                                ROUND(((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 1)
                        END
                    ) > 15 THEN 'emerging'
                    WHEN pm.share_percentage BETWEEN 5 AND 25 AND (
                        CASE 
                            WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                                CASE WHEN curr_year.yearly_penetration > 0 THEN 100.0 ELSE 0.0 END
                            ELSE 
                                ROUND(((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 1)
                        END
                    ) > 5 THEN 'growing'
                    WHEN pm.share_percentage >= 25 AND (
                        CASE 
                            WHEN prev_year.yearly_penetration IS NULL OR prev_year.yearly_penetration = 0 THEN 
                                CASE WHEN curr_year.yearly_penetration > 0 THEN 100.0 ELSE 0.0 END
                            ELSE 
                                ROUND(((curr_year.yearly_penetration - prev_year.yearly_penetration) / prev_year.yearly_penetration) * 100, 1)
                        END
                    ) < -5 THEN 'declining'
                    ELSE 'mature'
                END AS lifecycle_phase,
                CASE 
                    WHEN pm.unique_dishes = 0 THEN 0
                    ELSE ROUND(pm.base_dominant_count * 100.0 / pm.unique_dishes, 0)
                END AS base_dominant_percent,
                CASE 
                    WHEN pm.unique_dishes = 0 THEN 0
                    ELSE ROUND(pm.paired_dominant_count * 100.0 / pm.unique_dishes, 0)
                END AS paired_dominant_percent
            FROM pairing_metrics pm
            LEFT JOIN yearly_pairing_data prev_year ON pm.paired_ingredient = prev_year.paired_ingredient AND prev_year.year = {previous_year}
            LEFT JOIN yearly_pairing_data curr_year ON pm.paired_ingredient = curr_year.paired_ingredient AND curr_year.year = {CURRENT_YEAR}
        ),
        category_stats AS (
            SELECT 
                paired_ingredient,
                specific_category,
                general_category,
                COUNT(DISTINCT dish_id) AS category_dishes
            FROM ingredient_pairings
            WHERE {pairing_where}
            GROUP BY paired_ingredient, specific_category, general_category
        ),
        application_breakdown AS (
            SELECT 
                cs.paired_ingredient,
                STRING_AGG(
                    cs.specific_category || '|' || 
                    CASE 
                        WHEN gc.unique_dishes = 0 THEN '0'
                        ELSE ROUND(cs.category_dishes * 100.0 / NULLIF(gc.unique_dishes, 0), 0)::TEXT
                    END, 
                    ',' 
                    ORDER BY cs.category_dishes DESC
                ) AS applications_data,
                STRING_AGG(DISTINCT cs.general_category, ',') AS general_categories
            FROM (
                SELECT 
                    paired_ingredient,
                    specific_category,
                    general_category,
                    category_dishes,
                    ROW_NUMBER() OVER (PARTITION BY paired_ingredient ORDER BY category_dishes DESC) as rn
                FROM category_stats
            ) cs
            JOIN growth_calculation gc ON cs.paired_ingredient = gc.paired_ingredient
            WHERE cs.rn <= 4  -- Only top 4 specific categories
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
                FROM ingredient_pairings
                WHERE {pairing_where}
                GROUP BY paired_ingredient, dish_name, star_rating
            ) ranked_dishes
            WHERE rn <= 4
            GROUP BY paired_ingredient
        )
        SELECT 
            gc.paired_ingredient,
            gc.share_percentage,
            gc.growth_rate,
            gc.lifecycle_phase,
            gc.appeal_score,
            gc.avg_rating,
            gc.base_dominant_percent,
            gc.paired_dominant_percent,
            COALESCE(ab.applications_data, '') AS applications_data,
            COALESCE(ab.general_categories, '') AS general_categories,
            COALESCE(td.top_dishes_data, '') AS top_dishes_data,
            gc.unique_dishes
        FROM growth_calculation gc
        LEFT JOIN application_breakdown ab ON gc.paired_ingredient = ab.paired_ingredient
        LEFT JOIN top_dishes_agg td ON gc.paired_ingredient = td.paired_ingredient
        WHERE gc.unique_dishes >= 3
        """
        
        # Add additional filters to main query
        if additional_filters:
            main_query += " AND " + " AND ".join(additional_filters)
            
        # Add sorting and pagination
        main_query += f"""
        ORDER BY {sort_column} {sort_dir}
        LIMIT {limit} OFFSET {offset};
        """

        # Debug: Check if category filtering is working
        if category:
            debug_query = f"""
            SELECT COUNT(DISTINCT dish_id) as total_count,
                   COUNT(DISTINCT paired_ingredient) as unique_pairs
            FROM ingredient_pairings 
            WHERE {base_where}
            """
            debug_result = await execute_query(debug_query)
            print(f"Debug - Category '{category}' results: {debug_result['rows'][0] if debug_result['rows'] else 'No data'}")
        
        result = await execute_query(main_query)
        
        if not result["rows"]:
            return PairingsResponse(
                ingredient=ingredient,
                pairings=[],
                total_pairings=total_items,
                pagination=PaginationInfo(
                    current_page=page,
                    total_pages=total_pages,
                    total_items=total_items,
                    items_per_page=limit,
                    has_next=False,
                    has_previous=False
                )
            )

        print(f"Sample penetration data for {ingredient} (page {page}):")
        sample_penetrations = [row["share_percentage"] for row in result["rows"][:5]]
        print(f"Penetration debug: {sample_penetrations if sample_penetrations else 'No penetration data'}")

        pairings = []
        for row in result["rows"]:
            try:
                print(f"Processing row: {dict(row)}")
                
                paired_name = str(row["paired_ingredient"]).title()
                title = f"{ingredient.title()} + {paired_name}"
                
                # Parse applications data
                applications = []
                if row["applications_data"]:
                    app_pairs = row["applications_data"].split(',')
                    for pair in app_pairs[:10]:  # Limit to top 10
                        if '|' in pair:
                            app_name, app_percent = pair.split('|', 1)
                            try:
                                applications.append(TopApplication(
                                    application=app_name.strip(),
                                    percentage=float(app_percent)
                                ))
                            except ValueError:
                                continue

                # Parse top dishes
                dishes = []
                if row["top_dishes_data"]:
                    dishes = [dish.strip() for dish in row["top_dishes_data"].split(',')[:5]]

                # Parse general categories
                general_cats = []
                if row["general_categories"]:
                    general_cats = [cat.strip() for cat in row["general_categories"].split(',')]

                pairings.append(PairingData(
                    title=title,
                    share_percent=float(row["share_percentage"]) if row["share_percentage"] is not None else 0.0,
                    growth=float(row["growth_rate"]) if row["growth_rate"] is not None else 0.0,
                    lifecycle_phase=str(row["lifecycle_phase"]) if row["lifecycle_phase"] is not None else "unknown",
                    appeal_score=int(float(row["appeal_score"])) if row["appeal_score"] is not None else 0,
                    dominant_ingredient_percent=int(float(row["base_dominant_percent"])) if row["base_dominant_percent"] is not None else 0,
                    partner_ingredient_percent=int(float(row["paired_dominant_percent"])) if row["paired_dominant_percent"] is not None else 0,
                    partner_name=paired_name,
                    top_applications=applications,
                    top_dishes=dishes,
                    general_categories=general_cats
                ))
            except Exception as row_error:
                print(f"Error processing row {dict(row)}: {str(row_error)}")
                continue  # Skip this row and continue with the next one

        return PairingsResponse(
            ingredient=ingredient,
            pairings=pairings,
            total_pairings=total_items,
            pagination=PaginationInfo(
                current_page=page,
                total_pages=total_pages,
                total_items=total_items,
                items_per_page=limit,
                has_next=page < total_pages,
                has_previous=page > 1
            )
        )

    except Exception as e:
        print(f"Error in get_ingredient_pairings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")