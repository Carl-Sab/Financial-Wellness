import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QuestionnaireResponseCreate(BaseModel):
    user_id: uuid.UUID
    impulse_tendency_score: float | None = Field(default=None, ge=1, le=5)
    self_control_score: float | None = Field(default=None, ge=1, le=5)
    hedonic_score: float | None = Field(default=None, ge=1, le=7)
    utilitarian_score: float | None = Field(default=None, ge=1, le=7)
    raw_responses: dict[str, Any]
    instrument_version: str = "v1"


class QuestionnaireResponseUpdate(BaseModel):
    impulse_tendency_score: float | None = Field(default=None, ge=1, le=5)
    self_control_score: float | None = Field(default=None, ge=1, le=5)
    hedonic_score: float | None = Field(default=None, ge=1, le=7)
    utilitarian_score: float | None = Field(default=None, ge=1, le=7)
    raw_responses: dict[str, Any] | None = None
    instrument_version: str | None = None


class QuestionnaireResponseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    impulse_tendency_score: float | None
    self_control_score: float | None
    hedonic_score: float | None
    utilitarian_score: float | None
    raw_responses: dict[str, Any]
    instrument_version: str
    completed_at: datetime
