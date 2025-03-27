from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SensorBase(BaseModel):
    sensor_name: str
    active: bool


class SensorOverview(SensorBase):
    id: int
    location_id: Optional[int] = None
    location_name: Optional[str] = None

    class Config:
        orm_mode = True


class SensorData(BaseModel):
    id: int
    time: datetime
    value: float

    class Config:
        orm_mode = True


class AlertData(BaseModel):
    id: int
    event_type: str
    time: datetime
    description: str
    sensors_id: Optional[int] = None
    sensor_name: Optional[str] = None

    class Config:
        orm_mode = True


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"