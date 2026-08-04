import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from wellness.models.enums import ArousalLabel


class ArousalStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checkin_id: int
    user_id: uuid.UUID
    z_heart_rate: float | None
    z_hrv: float | None
    z_eda: float | None
    z_spo2: float | None
    z_skin_temp: float | None
    score: float | None
    label: ArousalLabel
    confidence: float | None
    metrics_used: int
    model_version: str
    computed_at: datetime
