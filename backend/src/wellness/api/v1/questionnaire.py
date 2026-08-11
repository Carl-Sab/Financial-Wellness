"""The real signup questionnaire — Blocks A-D, scored server-side.

Distinct from POST /api/v1/questionnaire-responses (questionnaire_responses.py):
that stays the unauthenticated, client-scored smoke-test CRUD endpoint it
always was — a caller there can submit whatever scores it likes. This is
the real flow: authenticated (the first route in the app to actually use
get_current_user), raw answers only accepted from the client, scores
computed here from wellness.services.questionnaire_scoring, and enforced
one-per-user by questionnaire_responses.user_id's unique constraint.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import get_current_user
from wellness.db import get_session
from wellness.models import QuestionnaireResponse, User
from wellness.schemas.questionnaire import QuestionnaireSubmitRequest
from wellness.schemas.questionnaire_responses import QuestionnaireResponseRead
from wellness.services.questionnaire_scoring import raw_responses_with_polarity, score_questionnaire

router = APIRouter(prefix="/questionnaire", tags=["questionnaire"])

INSTRUMENT_VERSION = "v1"


@router.post("", response_model=QuestionnaireResponseRead, status_code=201)
async def submit_questionnaire(
    payload: QuestionnaireSubmitRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuestionnaireResponse:
    scores = score_questionnaire(
        ibt_responses=[
            payload.ibt_1,
            payload.ibt_2,
            payload.ibt_3,
            payload.ibt_4,
            payload.ibt_5,
            payload.ibt_6,
            payload.ibt_7,
            payload.ibt_8,
            payload.ibt_9,
        ],
        sc_responses=[
            payload.sc_1,
            payload.sc_2,
            payload.sc_3,
            payload.sc_4,
            payload.sc_5,
            payload.sc_6,
            payload.sc_7,
            payload.sc_8,
            payload.sc_9,
            payload.sc_10,
            payload.sc_11,
            payload.sc_12,
            payload.sc_13,
        ],
        hed_responses=[
            payload.hed_1,
            payload.hed_2,
            payload.hed_3,
            payload.hed_4,
            payload.hed_5,
            payload.hed_6,
            payload.hed_7,
            payload.hed_8,
            payload.hed_9,
            payload.hed_10,
            payload.hed_11,
        ],
        util_responses=[payload.util_1, payload.util_2, payload.util_3, payload.util_4],
        norm_responses=[
            payload.norm_1,
            payload.norm_2,
            payload.norm_3,
            payload.norm_4,
            payload.norm_5,
            payload.norm_6,
            payload.norm_7,
            payload.norm_8,
        ],
    )

    response = QuestionnaireResponse(
        user_id=current_user.id,
        impulse_tendency_score=scores.impulse_tendency_score,
        self_control_score=scores.self_control_score,
        hedonic_score=scores.hedonic_score,
        utilitarian_score=scores.utilitarian_score,
        normative_eval_score=scores.normative_eval_score,
        raw_responses=raw_responses_with_polarity(payload.model_dump()),
        instrument_version=INSTRUMENT_VERSION,
    )

    try:
        session.add(response)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Questionnaire already completed") from exc

    await session.refresh(response)
    return response


@router.get("/me", response_model=QuestionnaireResponseRead)
async def get_my_questionnaire(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuestionnaireResponse:
    response = (
        await session.execute(
            select(QuestionnaireResponse).where(QuestionnaireResponse.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if response is None:
        raise HTTPException(status_code=404, detail="Questionnaire not completed")
    return response
