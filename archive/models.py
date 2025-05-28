# database/models.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class Share(BaseModel):
    share_percent: float
    change_percent: float
    # is_positive: bool







class ShareData(BaseModel):
    recipe_share_percent: float
    change_percent: float
    is_positive: bool




