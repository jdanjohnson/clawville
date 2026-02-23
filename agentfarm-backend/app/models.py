from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AgentRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=32, description="Agent display name")


class AgentResponse(BaseModel):
    id: int
    name: str
    api_token: str
    score: int
    sand_dollars: int
    created_at: str


class ParcelClaim(BaseModel):
    x: int = Field(..., ge=0, lt=20, description="X coordinate on world grid")
    y: int = Field(..., ge=0, lt=20, description="Y coordinate on world grid")


class PlantCrop(BaseModel):
    crop_type: str = Field(..., description="Crop type key, e.g. 'brain_coral'")
    local_x: int = Field(..., ge=0, lt=3, description="Plot X within parcel (0-2)")
    local_y: int = Field(..., ge=0, lt=3, description="Plot Y within parcel (0-2)")


class WaterParcel(BaseModel):
    local_x: Optional[int] = Field(None, ge=0, lt=3, description="Specific plot X to water (optional)")
    local_y: Optional[int] = Field(None, ge=0, lt=3, description="Specific plot Y to water (optional)")


class HarvestCrop(BaseModel):
    local_x: int = Field(..., ge=0, lt=3, description="Plot X within parcel (0-2)")
    local_y: int = Field(..., ge=0, lt=3, description="Plot Y within parcel (0-2)")


class StealRequest(BaseModel):
    target_parcel_id: int = Field(..., description="Parcel ID to steal from")
    local_x: int = Field(..., ge=0, lt=3, description="Plot X of mature crop to steal")
    local_y: int = Field(..., ge=0, lt=3, description="Plot Y of mature crop to steal")


class UnlockCropRequest(BaseModel):
    crop_type: str = Field(..., description="Crop type to unlock in Reef Emporium")


class PlotResponse(BaseModel):
    local_x: int
    local_y: int
    crop_type: Optional[str] = None
    crop_name: Optional[str] = None
    growth_stage: str
    planted_at: Optional[str] = None
    watered_at: Optional[str] = None
    ready_at: Optional[str] = None
    progress_pct: float = 0.0
    health: float = 1.0
    is_dead: bool = False


class ParcelResponse(BaseModel):
    id: int
    x: int
    y: int
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    claimed_at: Optional[str] = None
    price: int = 0
    plots: list[PlotResponse] = []


class WorldResponse(BaseModel):
    world_size: int
    total_parcels: int
    claimed_parcels: int
    total_agents: int
    parcels: list[ParcelResponse]


class ActivityResponse(BaseModel):
    id: int
    agent_name: Optional[str] = None
    action: str
    details: Optional[str] = None
    created_at: str


class LeaderboardEntry(BaseModel):
    rank: int
    agent_name: str
    score: int
    sand_dollars: int = 0


class CropInfo(BaseModel):
    key: str
    name: str
    grow_time_minutes: int
    decay_minutes: int
    points: int
    sand_dollar_yield: int
    plant_cost: int
    unlock_cost: int
    emoji: str
    color: str
    tier: int
    description: str


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="Chat message text")


class ChatMessageResponse(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    message: str
    created_at: str
