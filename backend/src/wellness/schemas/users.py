import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

# password_hash is intentionally never part of any schema here — see
# wellness.security for how UserCreate.password gets turned into it.


class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str = Field(min_length=8)
    date_of_birth: date
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str = "Asia/Beirut"
    currency: str = "LBP"


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    password: str | None = Field(default=None, min_length=8)
    date_of_birth: date | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str | None = None
    currency: str | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    date_of_birth: date
    phone: str | None
    address: str | None
    city: str | None
    country: str | None
    timezone: str
    currency: str
    is_active: bool
    created_at: datetime
