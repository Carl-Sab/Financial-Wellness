from typing import Literal

from pydantic import BaseModel, Field


class CheckinPredictionRead(BaseModel):
    checkin_id: int
    arousal_input_mode: Literal["manual", "detailed"]
    arousal_z: float
    arousal_case_score: float | None
    impulse_z: float
    overspending_probability: float = Field(ge=0, le=1)
    overspending_percentage: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high"]
    message: str
