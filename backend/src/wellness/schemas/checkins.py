import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wellness.models.enums import ValenceLevel

_READING_FIELDS = (
    "heart_rate",
    "hrv_ms",
    "eda_microsiemens",
    "spo2_percent",
    "skin_temp_c",
    "eeg_value",
)


class CheckinCreate(BaseModel):
    user_id: uuid.UUID
    category_code: str
    valence: ValenceLevel
    checkin_type: str = "pre_transaction"
    heart_rate: float | None = Field(default=None, ge=30, le=220)
    hrv_ms: float | None = Field(default=None, ge=1, le=300)
    eda_microsiemens: float | None = Field(default=None, ge=0, le=100)
    spo2_percent: float | None = Field(default=None, ge=70, le=100)
    skin_temp_c: float | None = Field(default=None, ge=30, le=43)
    eeg_value: float | None = None

    @model_validator(mode="after")
    def _at_least_one_reading(self) -> "CheckinCreate":
        if all(getattr(self, field) is None for field in _READING_FIELDS):
            raise ValueError("at least one physiological reading must be provided")
        return self


class CheckinUpdate(BaseModel):
    category_code: str | None = None
    valence: ValenceLevel | None = None
    checkin_type: str | None = None
    heart_rate: float | None = Field(default=None, ge=30, le=220)
    hrv_ms: float | None = Field(default=None, ge=1, le=300)
    eda_microsiemens: float | None = Field(default=None, ge=0, le=100)
    spo2_percent: float | None = Field(default=None, ge=70, le=100)
    skin_temp_c: float | None = Field(default=None, ge=30, le=43)
    eeg_value: float | None = None


class CheckinRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    category_code: str
    valence: ValenceLevel
    checkin_type: str
    heart_rate: float | None
    hrv_ms: float | None
    eda_microsiemens: float | None
    spo2_percent: float | None
    skin_temp_c: float | None
    eeg_value: float | None
    entered_at: datetime
