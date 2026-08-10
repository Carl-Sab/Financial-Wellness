import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserBaselineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    metric: str
    mean_value: float
    sd_value: float | None
    sample_n: int
    min_value: float | None
    max_value: float | None
    source: str
    computed_at: datetime
