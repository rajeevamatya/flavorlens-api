# database/models.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class Share(BaseModel):
    share_percent: float
    change_percent: float
    # is_positive: bool

class TextureAttribute(BaseModel):
    name: str
    value: float
    count: int
    avg_rating: float
    total_ratings: int
    scale: List[str]
    fill: str

class TextureTrend(BaseModel):
    year: str
    creamy: int = 0
    smooth: int = 0
    thick: int = 0
    frothy: int = 0
    powdery: int = 0

class TextureData(BaseModel):
    textureAttributesData: List[TextureAttribute]
    textureAttributeTrendData: List[TextureTrend]

class TemperatureDistribution(BaseModel):
    name: str
    value: float
    dish_count: int
    fill: str

class GeographicRegion(BaseModel):
    country: str
    adoption: float
    growth: float

class RegionalInsight(BaseModel):
    name: str
    adoption: float
    growth: float

class GeographicData(BaseModel):
    regions: List[GeographicRegion]
    regionalInsights: List[RegionalInsight]

class Format(BaseModel):
    format: str
    adoption: float
    dish_count: int
    top_applications: List[str]

class PopularApplication(BaseModel):
    name: str
    count: int
    rank: int

class FormatData(BaseModel):
    formats: List[Format]
    popularApplications: List[PopularApplication]

class Application(BaseModel):
    category: str
    application: str
    appealScore: float
    penetration: float
    growth: float
    ratings: float
    trend: str

# class CategoryDistribution(BaseModel):
#     name: str
#     value: float
#     dish_count: int
#     fill: str

class CategoryDistribution(BaseModel):
    name: str
    value: float
    dish_count: int
    count_2023: int
    yoy_growth_percentage: Optional[float]
    fill: str


class FlavorAttribute(BaseModel):
    attribute: str
    value: float

class SecondaryNote(BaseModel):
    note: str
    intensity: float

class SensoryDimension(BaseModel):
    dimension: str
    value: float

class FlavorProfile(BaseModel):
    coreAttributes: List[FlavorAttribute]
    secondaryNotes: List[SecondaryNote]
    sensoryDimensions: List[SensoryDimension]
    profileOverview: str
    sensoryExperience: str

class SubcategoryTrend(BaseModel):
    name: str
    color: str
    absoluteValues: List[int]

class SubcategoryData(BaseModel):
    years: List[int]
    categories: List[SubcategoryTrend]

class ShareData(BaseModel):
    recipe_share_percent: float
    change_percent: float
    is_positive: bool

class SeasonalAdoption(BaseModel):
    seasons: List[str]
    values: List[float]
    peakSeason: str
    yearRoundAppeal: int
    seasonalityIndex: int
    seasonalNotes: str

class LifecycleData(BaseModel):
    years: List[int]
    mentions: List[int]
    currentStage: str
    marketPenetration: float
    growthProjection: float
    innovationPotential: str
    seasonalAdoption: SeasonalAdoption

# class CuisineDistribution(BaseModel):
#     cuisine: str
#     percentage: float
#     growth: float
#     adoption: float

# In database/models.py
class CuisineDistribution(BaseModel):
    cuisine: str
    dish_count: int
    percentage: float
    growth: Optional[float]  # Can be null if no previous year data
    adoption: float

class CategoryPenetration(BaseModel):
    name: str
    penetration: float
    growth: float
    status: str
    color: str

class CategoryPenetrationData(BaseModel):
    categories: List[CategoryPenetration]

class TopApplication(BaseModel):
    name: str
    count: int
    growth: float

class TopRecipe(BaseModel):
    dish: str
    avg_rating: float
    num_ratings: int
    source: str

class TrendingData(BaseModel):
    topApplications: List[TopApplication]
    topRecipes: List[TopRecipe]
    innovationOpportunities: List[str]