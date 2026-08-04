from pydantic import BaseModel, ConfigDict

from wellness.models.enums import Level3


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    identity_level: Level3
    price_level: Level3
    advertising_level: Level3
    distribution_level: Level3
    stimuli_score: float | None
