from pydantic import BaseModel
from typing import List, Optional

class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class TrackDetail(BaseModel):
    track_id: int
    name: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    is_indoor: bool
    is_outdoor: bool
    is_sim: bool
    building_sqm: float
    disposable_income_pps: float
    catchment_area_size: Optional[float] = None
    sentiment_summary: Optional[str] = None

class WishlistUpdate(BaseModel):
    track_id: int
    action: str # "add" or "remove"
