from pydantic import BaseModel, Field

# Item wording lives in the frontend (and the source PDF), not here — this
# schema only cares about item ids and valid ranges. Blocks A and B are the
# two 1-5 scales; Blocks C and D are the two 1-7 scales. All 37 fields are
# required (no defaults): a missing item must 422, never silently score
# with a partial set. Field(ge=..., le=...) covers the out-of-range case
# (0, or 6 on a 1-5 scale) the same way — both are ordinary FastAPI 422s,
# not something requiring a custom check like the password field in
# RegisterRequest, since an item response isn't a secret worth keeping out
# of an error body.
#
# Block E (normative evaluation, norm_1..norm_8) is a 1-5 semantic
# differential per pair — same Field(ge=1, le=5) validation as Blocks A/B.


class QuestionnaireSubmitRequest(BaseModel):
    # Block A - Impulse buying tendency (1-5)
    ibt_1: int = Field(ge=1, le=5)
    ibt_2: int = Field(ge=1, le=5)
    ibt_3: int = Field(ge=1, le=5)
    ibt_4: int = Field(ge=1, le=5)
    ibt_5: int = Field(ge=1, le=5)
    ibt_6: int = Field(ge=1, le=5)
    ibt_7: int = Field(ge=1, le=5)
    ibt_8: int = Field(ge=1, le=5)
    ibt_9: int = Field(ge=1, le=5)

    # Block B - Self-control (1-5)
    sc_1: int = Field(ge=1, le=5)
    sc_2: int = Field(ge=1, le=5)
    sc_3: int = Field(ge=1, le=5)
    sc_4: int = Field(ge=1, le=5)
    sc_5: int = Field(ge=1, le=5)
    sc_6: int = Field(ge=1, le=5)
    sc_7: int = Field(ge=1, le=5)
    sc_8: int = Field(ge=1, le=5)
    sc_9: int = Field(ge=1, le=5)
    sc_10: int = Field(ge=1, le=5)
    sc_11: int = Field(ge=1, le=5)
    sc_12: int = Field(ge=1, le=5)
    sc_13: int = Field(ge=1, le=5)

    # Block C - Hedonic motives (1-7)
    hed_1: int = Field(ge=1, le=7)
    hed_2: int = Field(ge=1, le=7)
    hed_3: int = Field(ge=1, le=7)
    hed_4: int = Field(ge=1, le=7)
    hed_5: int = Field(ge=1, le=7)
    hed_6: int = Field(ge=1, le=7)
    hed_7: int = Field(ge=1, le=7)
    hed_8: int = Field(ge=1, le=7)
    hed_9: int = Field(ge=1, le=7)
    hed_10: int = Field(ge=1, le=7)
    hed_11: int = Field(ge=1, le=7)

    # Block D - Utilitarian motives (1-7)
    util_1: int = Field(ge=1, le=7)
    util_2: int = Field(ge=1, le=7)
    util_3: int = Field(ge=1, le=7)
    util_4: int = Field(ge=1, le=7)

    # Block E - Normative evaluation (1-5)
    norm_1: int = Field(ge=1, le=5)
    norm_2: int = Field(ge=1, le=5)
    norm_3: int = Field(ge=1, le=5)
    norm_4: int = Field(ge=1, le=5)
    norm_5: int = Field(ge=1, le=5)
    norm_6: int = Field(ge=1, le=5)
    norm_7: int = Field(ge=1, le=5)
    norm_8: int = Field(ge=1, le=5)
