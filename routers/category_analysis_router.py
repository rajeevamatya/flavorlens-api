# routers/category_analysis_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List, Optional
from config import CURRENT_YEAR  # Import CURRENT_YEAR from config

class CategoryDistribution(BaseModel):
    name: str
    value: float
    dish_count: int
    count_previous: int
    yoy_growth_percentage: Optional[float]

class CategoryPenetration(BaseModel):
    name: str
    penetration: float
    growth: float
    status: str

class CategoryAnalysis(BaseModel):
    highest_penetration: str
    highest_penetration_rate: float
    fastest_growing: str
    fastest_growth_rate: float
    total_categories: int
    hot_categories: int
    declining_categories: int
    avg_penetration: float

class CategoryInsight(BaseModel):
    category: str
    insight: str
    opportunity_type: str  # 'hot', 'rising', 'stable', 'declining'

class CategoryAnalysisResponse(BaseModel):
    ingredient: str
    distribution: List[CategoryDistribution]
    penetration: List[CategoryPenetration]
    analysis: CategoryAnalysis
    insights: List[CategoryInsight]
    summary: str

router = APIRouter()

@router.get("/category/analysis", response_model=CategoryAnalysisResponse)
async def get_category_analysis(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        previous_year = CURRENT_YEAR - 1
        
        # Distribution query - using overall data with growth from previous_year->CURRENT_YEAR
        category_distribution_query = f"""
        WITH overall_counts AS (
            -- Overall distribution across all years
            SELECT 
                general_category,
                COUNT(DISTINCT dish_id) AS total_dish_count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
            GROUP BY general_category
        ),
        growth_counts AS (
            -- Growth calculation: previous_year vs CURRENT_YEAR
            SELECT 
                general_category,
                COUNT(DISTINCT CASE WHEN year = {previous_year} THEN dish_id END) AS count_previous,
                COUNT(DISTINCT CASE WHEN year = {CURRENT_YEAR} THEN dish_id END) AS count_current
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
            GROUP BY general_category
        ),
        total_ingredient_dishes AS (
            SELECT COUNT(DISTINCT dish_id) AS total
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
        )
        SELECT 
            oc.general_category AS name,
            oc.total_dish_count AS dish_count,
            ROUND(oc.total_dish_count * 100.0 / NULLIF(tid.total, 0), 2) AS value,
            COALESCE(gc.count_previous, 0) AS count_previous,
            ROUND(
                CASE 
                    WHEN gc.count_previous = 0 OR gc.count_previous IS NULL THEN NULL
                    ELSE ((gc.count_current - gc.count_previous) * 100.0 / NULLIF(gc.count_previous, 0))
                END,
                2
            ) AS yoy_growth_percentage
        FROM overall_counts oc
        LEFT JOIN growth_counts gc ON oc.general_category = gc.general_category
        CROSS JOIN total_ingredient_dishes tid
        ORDER BY dish_count DESC;
        """
        
        # Penetration query - using overall data with growth from previous_year->CURRENT_YEAR
        category_penetration_query = f"""
        WITH ingredient_category_counts AS (
            -- Overall ingredient presence in each category
            SELECT 
                general_category,
                COUNT(DISTINCT dish_id) AS ingredient_dish_count
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND general_category IS NOT NULL
            GROUP BY general_category
        ),
        total_category_counts AS (
            -- Total dishes in each category (across all ingredients)
            SELECT 
                general_category,
                COUNT(DISTINCT dish_id) AS total_dish_count
            FROM ingredient_details
            WHERE general_category IS NOT NULL
            GROUP BY general_category
        ),
        growth_data AS (
            -- Growth calculation: previous_year vs CURRENT_YEAR for penetration
            SELECT 
                tc.general_category,
                COUNT(DISTINCT CASE WHEN id1.year = {previous_year} THEN id1.dish_id END) AS total_previous,
                COUNT(DISTINCT CASE WHEN id1.year = {CURRENT_YEAR} THEN id1.dish_id END) AS total_current,
                COUNT(DISTINCT CASE WHEN id1.year = {previous_year} AND id2.ingredient_name ILIKE {ingredient_pattern} THEN id1.dish_id END) AS ingredient_previous,
                COUNT(DISTINCT CASE WHEN id1.year = {CURRENT_YEAR} AND id2.ingredient_name ILIKE {ingredient_pattern} THEN id1.dish_id END) AS ingredient_current
            FROM ingredient_details id1
            LEFT JOIN ingredient_details id2 ON id1.dish_id = id2.dish_id AND id2.ingredient_name ILIKE {ingredient_pattern}
            JOIN total_category_counts tc ON id1.general_category = tc.general_category
            WHERE id1.general_category IS NOT NULL
            GROUP BY tc.general_category
        )
        SELECT 
            icc.general_category AS name,
            ROUND((icc.ingredient_dish_count * 100.0 / NULLIF(tcc.total_dish_count, 0)), 1) AS penetration,
            ROUND(
                CASE
                    WHEN gd.total_previous = 0 OR gd.ingredient_previous = 0 THEN 
                        CASE 
                            WHEN gd.ingredient_current > 0 THEN 100.0
                            ELSE 0.0
                        END
                    WHEN gd.total_current = 0 THEN 0.0
                    ELSE 
                        ((gd.ingredient_current * 100.0 / NULLIF(gd.total_current, 0)) - 
                         (gd.ingredient_previous * 100.0 / NULLIF(gd.total_previous, 0)))
                END,
                1
            ) AS growth,
            CASE
                WHEN gd.ingredient_previous = 0 AND gd.ingredient_current > 0 THEN 'Hot'
                WHEN gd.total_previous = 0 OR gd.ingredient_previous = 0 THEN 'New'
                WHEN gd.total_current = 0 THEN 'Declining'
                WHEN (gd.ingredient_current * 100.0 / NULLIF(gd.total_current, 0)) > 
                     (gd.ingredient_previous * 100.0 / NULLIF(gd.total_previous, 0)) * 1.25 THEN 'Hot'
                WHEN (gd.ingredient_current * 100.0 / NULLIF(gd.total_current, 0)) > 
                     (gd.ingredient_previous * 100.0 / NULLIF(gd.total_previous, 0)) * 1.1 THEN 'Rising'
                WHEN (gd.ingredient_current * 100.0 / NULLIF(gd.total_current, 0)) >= 
                     (gd.ingredient_previous * 100.0 / NULLIF(gd.total_previous, 0)) * 0.9 THEN 'Stable'
                ELSE 'Declining'
            END AS status
        FROM ingredient_category_counts icc
        JOIN total_category_counts tcc ON icc.general_category = tcc.general_category
        LEFT JOIN growth_data gd ON icc.general_category = gd.general_category
        ORDER BY penetration DESC
        LIMIT 10;
        """
        
        # Execute queries
        dist_result = await execute_query(
            category_distribution_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        pen_result = await execute_query(
            category_penetration_query,
            options=QueryOptions(cacheable=True, ttl=3600000)
        )
        
        if not dist_result["rows"] or not pen_result["rows"]:
            raise HTTPException(status_code=404, detail=f"No category data found for ingredient: {ingredient}")
        
        # Process distribution data
        distribution = []
        for row in dist_result["rows"]:
            distribution.append(CategoryDistribution(
                name=str(row["name"]),
                value=float(row["value"]) if row["value"] is not None else 0.0,
                dish_count=int(row["dish_count"]),
                count_previous=int(row["count_previous"]) if row["count_previous"] is not None else 0,
                yoy_growth_percentage=float(row["yoy_growth_percentage"]) if row["yoy_growth_percentage"] is not None else None
            ))
        
        # Process penetration data
        penetration = []
        for row in pen_result["rows"]:
            penetration.append(CategoryPenetration(
                name=str(row["name"]),
                penetration=float(row["penetration"]) if row["penetration"] is not None else 0.0,
                growth=float(row["growth"]) if row["growth"] is not None else 0.0,
                status=str(row["status"])
            ))
        
        # Generate analysis
        analysis = calculate_category_analysis(penetration)
        insights = generate_category_insights(penetration, distribution)
        summary = generate_summary(ingredient, penetration, analysis)
        
        return CategoryAnalysisResponse(
            ingredient=ingredient,
            distribution=distribution,
            penetration=penetration,
            analysis=analysis,
            insights=insights,
            summary=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category analysis data")


def calculate_category_analysis(penetration: List[CategoryPenetration]) -> CategoryAnalysis:
    """Calculate comprehensive category analysis"""
    
    if not penetration:
        return CategoryAnalysis(
            highest_penetration="Unknown",
            highest_penetration_rate=0.0,
            fastest_growing="Unknown",
            fastest_growth_rate=0.0,
            total_categories=0,
            hot_categories=0,
            declining_categories=0,
            avg_penetration=0.0
        )
    
    # Find highest penetration
    highest_pen = max(penetration, key=lambda x: x.penetration)
    
    # Find fastest growing
    fastest_growing = max(penetration, key=lambda x: x.growth)
    
    # Count categories by status
    hot_count = len([cat for cat in penetration if cat.status in ['Hot', 'Rising']])
    declining_count = len([cat for cat in penetration if cat.status == 'Declining'])
    
    # Calculate average penetration
    avg_penetration = sum(cat.penetration for cat in penetration) / len(penetration)
    
    return CategoryAnalysis(
        highest_penetration=highest_pen.name,
        highest_penetration_rate=highest_pen.penetration,
        fastest_growing=fastest_growing.name,
        fastest_growth_rate=fastest_growing.growth,
        total_categories=len(penetration),
        hot_categories=hot_count,
        declining_categories=declining_count,
        avg_penetration=avg_penetration
    )


def generate_category_insights(penetration: List[CategoryPenetration], distribution: List[CategoryDistribution]) -> List[CategoryInsight]:
    """Generate insights for each category"""
    
    insights = []
    
    # Top 5 categories by penetration
    for category in penetration[:5]:
        # Find corresponding distribution data
        dist_data = next((d for d in distribution if d.name == category.name), None)
        
        insight = ""
        opportunity_type = category.status.lower()
        
        if category.status == 'Hot':
            if category.growth > 50:
                insight = f"Explosive growth (+{category.growth:.1f}pp) with {category.penetration:.1f}% penetration"
            else:
                insight = f"Strong momentum (+{category.growth:.1f}pp) in established market"
        elif category.status == 'Rising':
            insight = f"Growing adoption (+{category.growth:.1f}pp) with {category.penetration:.1f}% penetration"
        elif category.status == 'Stable':
            if category.penetration > 50:
                insight = f"Mature market with {category.penetration:.1f}% penetration, stable performance"
            else:
                insight = f"Steady {category.penetration:.1f}% penetration, potential for growth"
        elif category.status == 'Declining':
            insight = f"Declining adoption ({category.growth:.1f}pp) despite {category.penetration:.1f}% penetration"
        else:
            insight = f"Current penetration: {category.penetration:.1f}%"
        
        # Add dish count context if available
        if dist_data and dist_data.dish_count > 0:
            insight += f" ({dist_data.dish_count} dishes)"
        
        insights.append(CategoryInsight(
            category=category.name,
            insight=insight,
            opportunity_type=opportunity_type
        ))
    
    return insights


def generate_summary(ingredient: str, penetration: List[CategoryPenetration], analysis: CategoryAnalysis) -> str:
    """Generate a comprehensive summary of category analysis"""
    
    if not penetration:
        return f"No category analysis data available for {ingredient}."
    
    summary = f"{ingredient.title()} shows strong presence across {analysis.total_categories} food service categories. "
    
    # Top performer insight
    summary += f"{analysis.highest_penetration} leads with {analysis.highest_penetration_rate:.1f}% penetration, "
    
    # Growth insight
    if analysis.fastest_growth_rate > 5:
        summary += f"while {analysis.fastest_growing} demonstrates exceptional growth (+{analysis.fastest_growth_rate:.1f}pp). "
    elif analysis.fastest_growth_rate > 1:
        summary += f"with {analysis.fastest_growing} showing solid growth (+{analysis.fastest_growth_rate:.1f}pp). "
    else:
        summary += f"with generally stable performance across categories. "
    
    # Market health
    if analysis.hot_categories > analysis.declining_categories:
        summary += f"Market shows positive momentum with {analysis.hot_categories} hot/rising categories "
    else:
        summary += f"Market shows mixed signals with {analysis.declining_categories} declining categories "
    
    summary += f"and {analysis.avg_penetration:.1f}% average penetration rate."
    
    return summary