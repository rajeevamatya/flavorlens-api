# routers/flavor_profile_router.py
from fastapi import APIRouter, HTTPException, Query
from database.connection import execute_query, QueryOptions
from database.models import FlavorProfile, FlavorAttribute, SecondaryNote, SensoryDimension
import asyncio

router = APIRouter()

@router.get("/flavor-profile", response_model=FlavorProfile)
async def get_flavor_profile(ingredient: str = Query(..., description="Ingredient name")):
    try:
        ingredient_pattern = f"'%{ingredient}%'"
        
        # Core attributes query
        core_attributes_query = f"""
        WITH ingredient_dishes AS (
            SELECT DISTINCT
                d.dish_id,
                d.dish_name,
                d.description,
                d.flavor_notes,
                di.ingredient_id
            FROM 
                flavorlens.main.dishes d
            JOIN 
                flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
            WHERE 
                di.name ILIKE {ingredient_pattern}
        ),
        flavor_attributes AS (
            SELECT unnest(['Sweet', 'Bitter', 'Salty', 'Sour', 'Umami', 
                          'Astringent', 'Vegetal', 'Earthy']) AS attribute
        ),
        attribute_mentions AS (
            SELECT
                fa.attribute,
                COUNT(id.*) AS mention_count
            FROM
                flavor_attributes fa
            CROSS JOIN ingredient_dishes id
            WHERE
                (id.description ILIKE '%' || fa.attribute || '%' OR
                 id.flavor_notes ILIKE '%' || fa.attribute || '%')
            GROUP BY
                fa.attribute
        )
        SELECT
            attribute,
            GREATEST(10, LEAST(90, (mention_count * 10))) AS value
        FROM
            attribute_mentions
        ORDER BY
            value DESC;
        """
        
        # Secondary notes query
        secondary_notes_query = f"""
        WITH ingredient_dishes AS (
            SELECT DISTINCT
                d.dish_id,
                d.dish_name,
                d.description,
                d.flavor_notes,
                di.ingredient_id
            FROM 
                flavorlens.main.dishes d
            JOIN 
                flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
            WHERE 
                di.name ILIKE {ingredient_pattern}
        ),
        secondary_notes AS (
            SELECT unnest(['Grassy', 'Seaweed', 'Nutty', 'Floral', 'Cocoa', 'Spinach',
                          'Citrus', 'Fruity', 'Woody', 'Spicy', 'Smoky', 'Creamy']) AS note
        ),
        note_mentions AS (
            SELECT
                sn.note,
                COUNT(id.*) AS mention_count
            FROM
                secondary_notes sn
            CROSS JOIN ingredient_dishes id
            WHERE
                (id.description ILIKE '%' || sn.note || '%' OR
                 id.flavor_notes ILIKE '%' || sn.note || '%')
            GROUP BY
                sn.note
        )
        SELECT
            note,
            GREATEST(10, LEAST(95, (mention_count * 15))) AS intensity
        FROM
            note_mentions
        ORDER BY
            intensity DESC
        LIMIT 6;
        """
        
        # Sensory dimensions query
        sensory_dimensions_query = f"""
        WITH ingredient_dishes AS (
            SELECT DISTINCT
                d.dish_id,
                d.dish_name,
                d.star_rating,
                d.description,
                d.flavor_notes,
                di.ingredient_id
            FROM 
                flavorlens.main.dishes d
            JOIN 
                flavorlens.main.dish_ingredients di ON d.dish_id = di.dish_id
            WHERE 
                di.name ILIKE {ingredient_pattern}
        ),
        sensory_dimensions AS (
            SELECT unnest(['Taste Intensity', 'Aroma Impact', 'Mouthfeel', 
                          'Persistence', 'Heat/Spice', 'Visual Impact']) AS dimension
        ),
        dimension_values AS (
            SELECT
                sd.dimension,
                CASE 
                    WHEN sd.dimension = 'Taste Intensity' THEN 
                        (SELECT AVG(CAST(star_rating AS FLOAT)) * 15 FROM ingredient_dishes WHERE description ILIKE '%flavor%' OR description ILIKE '%taste%')
                    WHEN sd.dimension = 'Aroma Impact' THEN
                        (SELECT AVG(CAST(star_rating AS FLOAT)) * 15 FROM ingredient_dishes WHERE description ILIKE '%aroma%' OR description ILIKE '%smell%')
                    WHEN sd.dimension = 'Mouthfeel' THEN
                        (SELECT AVG(CAST(star_rating AS FLOAT)) * 15 FROM ingredient_dishes WHERE description ILIKE '%texture%' OR description ILIKE '%mouth%')
                    WHEN sd.dimension = 'Persistence' THEN
                        (SELECT AVG(CAST(star_rating AS FLOAT)) * 15 FROM ingredient_dishes WHERE description ILIKE '%linger%' OR description ILIKE '%lasting%')
                    WHEN sd.dimension = 'Heat/Spice' THEN
                        (SELECT AVG(CAST(star_rating AS FLOAT)) * 15 FROM ingredient_dishes WHERE description ILIKE '%spice%' OR description ILIKE '%heat%')
                    WHEN sd.dimension = 'Visual Impact' THEN
                        (SELECT AVG(CAST(star_rating AS FLOAT)) * 15 FROM ingredient_dishes WHERE description ILIKE '%color%' OR description ILIKE '%visual%')
                    ELSE 50
                END AS calculated_value
            FROM 
                sensory_dimensions sd
        )
        SELECT
            dimension,
            COALESCE(GREATEST(10, LEAST(95, calculated_value)), 50) AS value
        FROM 
            dimension_values;
        """
        
        # Execute all queries
        core_result, secondary_result, sensory_result = await asyncio.gather(
            execute_query(core_attributes_query),
            execute_query(secondary_notes_query),
            execute_query(sensory_dimensions_query)
        )
        
        # Process core attributes
        core_attributes = []
        if core_result["rows"]:
            for row in core_result["rows"]:
                core_attributes.append(FlavorAttribute(
                    attribute=row["attribute"],
                    value=float(row["value"])
                ))
        
        # Process secondary notes
        secondary_notes = []
        if secondary_result["rows"]:
            for row in secondary_result["rows"]:
                secondary_notes.append(SecondaryNote(
                    note=row["note"],
                    intensity=float(row["intensity"])
                ))
        
        # Process sensory dimensions
        sensory_dimensions = []
        if sensory_result["rows"]:
            for row in sensory_result["rows"]:
                sensory_dimensions.append(SensoryDimension(
                    dimension=row["dimension"],
                    value=float(row["value"])
                ))
        
        # Generate profile overview
        def generate_profile_overview():
            high_attributes = [attr.attribute.lower() for attr in core_attributes if attr.value > 70]
            medium_attributes = [attr.attribute.lower() for attr in core_attributes if 40 <= attr.value <= 70]
            
            description = f"{ingredient.capitalize()} presents a "
            
            if high_attributes:
                description += f"bold, {' and '.join(high_attributes)} profile"
                if medium_attributes:
                    description += f" with moderate {' and '.join(medium_attributes)}"
            elif medium_attributes:
                description += f"balanced profile with {' and '.join(medium_attributes)} characteristics"
            else:
                description += "subtle, nuanced flavor profile"
            
            if secondary_notes:
                top_notes = [note.note.lower() for note in secondary_notes[:3]]
                description += f". Secondary notes include {', '.join(top_notes)} characteristics."
            
            return description
        
        # Generate sensory experience
        def generate_sensory_experience():
            if not sensory_dimensions:
                return f"The {ingredient} sensory experience is distinctive and engaging."
                
            top_dimensions = sorted(sensory_dimensions, key=lambda x: x.value, reverse=True)[:2]
            top_dimension_names = [dim.dimension.lower() for dim in top_dimensions]
            
            description = f"The {ingredient} sensory experience is dominated by its {' and '.join(top_dimension_names)}. "
            
            # Add details about specific dimensions
            aroma = next((d for d in sensory_dimensions if d.dimension == 'Aroma Impact'), None)
            mouthfeel = next((d for d in sensory_dimensions if d.dimension == 'Mouthfeel'), None)
            persistence = next((d for d in sensory_dimensions if d.dimension == 'Persistence'), None)
            
            if aroma:
                description += "Aroma is pronounced and distinctive. " if aroma.value > 60 else "Aroma is subtle but present. "
            
            if mouthfeel:
                description += "The texture creates a notable mouthfeel experience. " if mouthfeel.value > 60 else "The texture contributes moderate mouthfeel characteristics. "
            
            if persistence:
                description += "Flavor notes are highly persistent with a lingering finish." if persistence.value > 60 else "Flavor notes are moderately persistent on the palate."
            
            return description
        
        return FlavorProfile(
            coreAttributes=core_attributes,
            secondaryNotes=secondary_notes,
            sensoryDimensions=sensory_dimensions,
            profileOverview=generate_profile_overview(),
            sensoryExperience=generate_sensory_experience()
        )
        
    except Exception as e:
        print(f"Error fetching flavor profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch flavor profile data")

