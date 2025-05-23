CREATE TABLE ingredient_details AS
SELECT
    di.dish_id,
    di.ingredient_id,
    di.name  AS ingredient_name,
    di.format AS ingredient_format,
    di.type   AS ingredient_type,
    di.ingredient_role,
    di.cooking_technique AS ingredient_cooking_technique,
    di.flavor_role,
    di.alternatives,
    di.flavor_notes,

    -- Enriched dish information
    d.dish_name,
    d.general_category,
    d.specific_category,
    d.cuisine,
    d.country,
    d.serving_temperature,
    d.cooking_technique AS dish_cooking_technique,
    d.season,
    d.source,
    d.date_created AS dish_date_created,
    d.star_rating,
    d.num_ratings,
    d.num_reviews,

    -- Calendar dimensions (based on dish_date_created)
    EXTRACT(YEAR    FROM d.date_created) AS year,
    EXTRACT(MONTH   FROM d.date_created) AS month,
    EXTRACT(QUARTER FROM d.date_created) AS quarter
FROM dish_ingredients di
JOIN dishes d
  ON di.dish_id = d.dish_id;
