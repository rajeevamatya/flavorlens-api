# routers/category_trends_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from pydantic import BaseModel
from typing import List
import asyncio

class CategoryTrend(BaseModel):
    name: str
    adoption_percentages: List[float]

class CategoryAnalysis(BaseModel):
    top_performer: str
    top_performer_rate: float
    fastest_growing: str
    fastest_growth_rate: float
    most_consistent: str
    total_categories: int
    avg_adoption_rate: float

class CategoryInsight(BaseModel):
    category: str
    insight: str
    growth_pattern: str  # 'strong_growth', 'steady_growth', 'stable', 'declining'

class CategoryTrendResponse(BaseModel):
    ingredient: str
    years: List[int]
    categories: List[CategoryTrend]
    analysis: CategoryAnalysis
    insights: List[CategoryInsight]
    summary: str

router = APIRouter()

@router.get("/category/trends", response_model=CategoryTrendResponse)
async def get_category_trends(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        years_query = f"""
        SELECT DISTINCT year
        FROM ingredient_details
        WHERE year >= 2018
            AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
        ORDER BY year ASC
        LIMIT 7;
        """
        
        category_trends_query = f"""
        WITH yearly_category_totals AS (
            SELECT 
                year,
                COALESCE(general_category, 'Other') AS category,
                COUNT(DISTINCT dish_id) AS total_dishes
            FROM ingredient_details
            WHERE year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND general_category IS NOT NULL
            GROUP BY year, general_category
        ),
        yearly_category_ingredient AS (
            SELECT 
                year,
                COALESCE(general_category, 'Other') AS category,
                COUNT(DISTINCT dish_id) AS ingredient_dishes
            FROM ingredient_details
            WHERE ingredient_name ILIKE {ingredient_pattern}
                AND year >= 2018
                AND year <= EXTRACT(YEAR FROM CURRENT_DATE)
                AND general_category IS NOT NULL
            GROUP BY year, general_category
        )
        SELECT 
            yct.year,
            yct.category AS name,
            ROUND(
                COALESCE(yci.ingredient_dishes, 0) * 100.0 / NULLIF(yct.total_dishes, 0), 
                2
            ) AS adoption_percentage
        FROM yearly_category_totals yct
        LEFT JOIN yearly_category_ingredient yci 
            ON yct.year = yci.year AND yct.category = yci.category
        ORDER BY yct.year ASC, adoption_percentage DESC;
        """
        
        # Execute queries
        years_result, trends_result = await asyncio.gather(
            execute_query(years_query, options=QueryOptions(cacheable=True, ttl=3600000)),
            execute_query(category_trends_query, options=QueryOptions(cacheable=True, ttl=3600000))
        )
        
        if not years_result["rows"] or not trends_result["rows"]:
            raise HTTPException(status_code=404, detail=f"No category trends data found for ingredient: {ingredient}")
        
        years = [int(row["year"]) for row in years_result["rows"]]
        
        # Process trend data by category
        category_map = {}
        
        # Group data by category
        for row in trends_result["rows"]:
            category_name = str(row["name"])
            if category_name not in category_map:
                category_map[category_name] = {
                    "name": category_name,
                    "adoption_percentages": [0.0] * len(years)
                }
            
            # Find the index for this year
            year_index = years.index(int(row["year"])) if int(row["year"]) in years else -1
            if year_index >= 0:
                category_map[category_name]["adoption_percentages"][year_index] = float(row["adoption_percentage"] or 0.0)
        
        # Convert to list and take top 5 categories by total adoption
        sorted_categories = sorted(
            category_map.values(),
            key=lambda x: sum(x["adoption_percentages"]),
            reverse=True
        )[:5]
        
        categories = [
            CategoryTrend(
                name=category["name"],
                adoption_percentages=category["adoption_percentages"]
            )
            for category in sorted_categories
        ]
        
        # Generate analysis
        analysis = calculate_category_analysis(categories)
        insights = generate_category_insights(categories, years)
        summary = generate_summary(ingredient, categories, analysis)
        
        return CategoryTrendResponse(
            ingredient=ingredient,
            years=years,
            categories=categories,
            analysis=analysis,
            insights=insights,
            summary=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch category trends data")


def calculate_category_analysis(categories: List[CategoryTrend]) -> CategoryAnalysis:
    """Calculate comprehensive category analysis"""
    
    if not categories:
        return CategoryAnalysis(
            top_performer="Unknown",
            top_performer_rate=0.0,
            fastest_growing="Unknown",
            fastest_growth_rate=0.0,
            most_consistent="Unknown",
            total_categories=0,
            avg_adoption_rate=0.0
        )

    # Find top performer (highest current adoption)
    top_performer = max(categories, key=lambda x: x.adoption_percentages[-1] if x.adoption_percentages else 0)
    top_performer_rate = top_performer.adoption_percentages[-1] if top_performer.adoption_percentages else 0

    # Find fastest growing (highest growth rate)
    fastest_growing = categories[0]
    fastest_growth_rate = 0.0

    for category in categories:
        values = category.adoption_percentages
        if len(values) > 1:
            first_value = next((v for v in values if v > 0), 0)
            last_value = values[-1] if values else 0
            
            if first_value > 0:
                growth_rate = ((last_value - first_value) / first_value) * 100
                if growth_rate > fastest_growth_rate:
                    fastest_growth_rate = growth_rate
                    fastest_growing = category

    # Find most consistent (lowest coefficient of variation)
    most_consistent = categories[0]
    lowest_cv = float('inf')

    for category in categories:
        values = [v for v in category.adoption_percentages if v > 0]
        if len(values) > 1:
            mean_val = sum(values) / len(values)
            if mean_val > 0:
                std_dev = (sum((v - mean_val) ** 2 for v in values) / len(values)) ** 0.5
                cv = std_dev / mean_val  # Coefficient of variation
                
                if cv < lowest_cv:
                    lowest_cv = cv
                    most_consistent = category

    # Calculate average adoption rate
    all_values = [v for cat in categories for v in cat.adoption_percentages if v > 0]
    avg_adoption_rate = sum(all_values) / len(all_values) if all_values else 0.0

    return CategoryAnalysis(
        top_performer=top_performer.name,
        top_performer_rate=top_performer_rate,
        fastest_growing=fastest_growing.name,
        fastest_growth_rate=fastest_growth_rate,
        most_consistent=most_consistent.name,
        total_categories=len(categories),
        avg_adoption_rate=avg_adoption_rate
    )


def generate_category_insights(categories: List[CategoryTrend], years: List[int]) -> List[CategoryInsight]:
    """Generate insights for each category"""
    
    insights = []
    
    for category in categories[:4]:  # Top 4 categories
        values = category.adoption_percentages
        
        if not values or len(values) < 2:
            insights.append(CategoryInsight(
                category=category.name,
                insight=f"Current adoption: {values[-1]:.1f}%" if values else "No data available",
                growth_pattern="stable"
            ))
            continue
            
        last_value = values[-1]
        first_value = next((v for v in values if v > 0), 0)
        recent_change = values[-1] - values[-2] if len(values) > 1 else 0
        
        # Determine growth pattern and insight
        if first_value > 0:
            total_growth = ((last_value - first_value) / first_value) * 100
            
            if total_growth > 50:
                pattern = "strong_growth"
                insight = f"Strong growth trajectory (+{total_growth:.0f}% since {years[0]})"
            elif total_growth > 20:
                pattern = "steady_growth"
                insight = f"Steady growth (+{total_growth:.0f}% since {years[0]})"
            elif recent_change > 1:
                pattern = "steady_growth"
                insight = f"Recent growth (+{recent_change:.1f}% last year)"
            elif recent_change < -1:
                pattern = "declining"
                insight = f"Recent decline ({recent_change:.1f}% last year)"
            else:
                pattern = "stable"
                insight = f"Stable at {last_value:.1f}% adoption"
        else:
            pattern = "stable"
            insight = f"Current adoption: {last_value:.1f}%"
        
        insights.append(CategoryInsight(
            category=category.name,
            insight=insight,
            growth_pattern=pattern
        ))
    
    return insights


def generate_summary(ingredient: str, categories: List[CategoryTrend], analysis: CategoryAnalysis) -> str:
    """Generate a comprehensive summary of category trends"""
    
    if not categories:
        return f"No category trend data available for {ingredient}."
    
    summary = f"{ingredient.title()} shows varied adoption across {analysis.total_categories} food service categories. "
    
    # Top performer insight
    summary += f"{analysis.top_performer} leads with {analysis.top_performer_rate:.1f}% adoption, "
    
    # Growth insight
    if analysis.fastest_growth_rate > 30:
        summary += f"while {analysis.fastest_growing} demonstrates exceptional growth (+{analysis.fastest_growth_rate:.0f}%). "
    elif analysis.fastest_growth_rate > 10:
        summary += f"with {analysis.fastest_growing} showing solid growth (+{analysis.fastest_growth_rate:.0f}%). "
    else:
        summary += f"with generally stable category performance. "
    
    # Overall performance
    if analysis.avg_adoption_rate > 10:
        summary += f"The ingredient maintains strong market presence with {analysis.avg_adoption_rate:.1f}% average adoption "
    elif analysis.avg_adoption_rate > 5:
        summary += f"The ingredient shows moderate market presence with {analysis.avg_adoption_rate:.1f}% average adoption "
    else:
        summary += f"The ingredient has emerging market presence with {analysis.avg_adoption_rate:.1f}% average adoption "
    
    summary += f"across analyzed categories."
    
    return summary