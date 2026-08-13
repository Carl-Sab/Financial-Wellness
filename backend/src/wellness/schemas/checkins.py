import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from wellness.models.enums import ValenceLevel

_DETAILED_AROUSAL_FIELDS = (
    "perceived_heart_rate",
    "perceived_heartbeat_steadiness",
    "perceived_sweating",
    "perceived_respiration",
    "perceived_temperature_difference",
)

ArousalInputMode = Literal["manual", "detailed"]
ArousalValue = Literal[-2, -1, 0, 1, 2]


class CheckinCreate(BaseModel):
    category_code: str
    valence: ValenceLevel
    arousal_input_mode: ArousalInputMode
    arousal_z: ArousalValue | None = None
    perceived_heart_rate: ArousalValue | None = None
    perceived_heartbeat_steadiness: ArousalValue | None = None
    perceived_sweating: ArousalValue | None = None
    perceived_respiration: ArousalValue | None = None
    perceived_temperature_difference: ArousalValue | None = None

    @model_validator(mode="after")
    def _validate_arousal_input(self) -> "CheckinCreate":
        detailed_values = [getattr(self, field) for field in _DETAILED_AROUSAL_FIELDS]

        if self.arousal_input_mode == "manual":
            if self.arousal_z is None:
                raise ValueError("manual arousal input requires arousal_z")
            if any(value is not None for value in detailed_values):
                raise ValueError("manual arousal input cannot include detailed arousal values")
            return self

        if self.arousal_z is not None:
            raise ValueError("detailed arousal input cannot include arousal_z")
        if any(value is None for value in detailed_values):
            raise ValueError("detailed arousal input requires all five arousal values")
        return self


class CheckinUpdate(BaseModel):
    category_code: str | None = None
    valence: ValenceLevel | None = None


class CheckinRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    category_code: str
    valence: ValenceLevel
    arousal_input_mode: ArousalInputMode | None
    arousal_z: ArousalValue | None
    perceived_heart_rate: ArousalValue | None
    perceived_heartbeat_steadiness: ArousalValue | None
    perceived_sweating: ArousalValue | None
    perceived_respiration: ArousalValue | None
    perceived_temperature_difference: ArousalValue | None
    entered_at: datetime
