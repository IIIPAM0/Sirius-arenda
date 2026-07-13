from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ---------- Rooms ----------

class RoomBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    capacity: int = Field(..., gt=0)
    equipment: list[str] = Field(default_factory=list)


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    capacity: int | None = Field(default=None, gt=0)
    equipment: list[str] | None = None


class Room(RoomBase):
    id: int


# ---------- Bookings ----------

class BookingStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"


class BookingCreate(BaseModel):
    room_id: int
    start_time: datetime
    end_time: datetime
    username: str = Field(..., min_length=1, max_length=200)

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: datetime, info):
        start = info.data.get("start_time")
        if start is not None and v <= start:
            raise ValueError("end_time должен быть позже start_time")
        return v


class Booking(BaseModel):
    id: int
    room_id: int
    start_time: datetime
    end_time: datetime
    username: str
    status: BookingStatus
    owner_id: int | None = None  # id пользователя, создавшего бронь (для прав доступа)


# ---------- Users / Auth ----------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class UserPublic(BaseModel):
    id: int
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ErrorResponse(BaseModel):
    detail: str
