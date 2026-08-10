import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

_READING_FIELDS = ("heart_rate", "hrv_ms", "spo2_percent")


class SampleCreate(BaseModel):
    user_id: uuid.UUID
    ts: datetime
    heart_rate: float | None = Field(default=None, ge=30, le=220)
    hrv_ms: float | None = Field(default=None, ge=1, le=300)
    spo2_percent: float | None = Field(default=None, ge=70, le=100)
    data_source: str = "healthkit"

    @model_validator(mode="after")
    def _at_least_one_reading(self) -> "SampleCreate":
        if all(getattr(self, field) is None for field in _READING_FIELDS):
            raise ValueError("at least one reading must be provided")
        return self


class SampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    ts: datetime
    heart_rate: float | None
    hrv_ms: float | None
    spo2_percent: float | None
    data_source: str
    ingested_at: datetime


class SampleBatchResult(BaseModel):
    received: int
    inserted: int
    skipped: int


class SampleAverageBucket(BaseModel):
    period_start: datetime
    avg_heart_rate: float | None
    min_heart_rate: float | None
    max_heart_rate: float | None
    count: int
