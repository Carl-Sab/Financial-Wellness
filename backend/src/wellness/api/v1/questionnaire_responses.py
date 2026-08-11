# Smoke-test CRUD for questionnaire_responses — distinct from the real,
# server-scored signup flow at POST /api/v1/questionnaire (questionnaire.py).
# This one still accepts client-supplied scores; it's just no longer
# readable/writable by anyone but the row's own user.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import QuestionnaireResponse, User
from wellness.schemas.questionnaire_responses import (
    QuestionnaireResponseCreate,
    QuestionnaireResponseRead,
    QuestionnaireResponseUpdate,
)

router = APIRouter(prefix="/questionnaire-responses", tags=["questionnaire_responses"])


@router.post("", response_model=QuestionnaireResponseRead, status_code=201)
async def create_questionnaire_response(
    payload: QuestionnaireResponseCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuestionnaireResponse:
    response = QuestionnaireResponse(**payload.model_dump(), user_id=current_user.id)
    session.add(response)
    await commit_or_409(session)
    await session.refresh(response)
    return response


@router.get("", response_model=list[QuestionnaireResponseRead])
async def list_questionnaire_responses(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[QuestionnaireResponse]:
    result = await session.execute(
        select(QuestionnaireResponse)
        .where(QuestionnaireResponse.user_id == current_user.id)
        .order_by(QuestionnaireResponse.completed_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{response_id}", response_model=QuestionnaireResponseRead)
async def get_questionnaire_response(
    response_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuestionnaireResponse:
    response = await session.get(QuestionnaireResponse, response_id)
    if response is None or response.user_id != current_user.id:
        raise not_found("questionnaire_response")
    return response


@router.patch("/{response_id}", response_model=QuestionnaireResponseRead)
async def update_questionnaire_response(
    response_id: int,
    payload: QuestionnaireResponseUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuestionnaireResponse:
    response = await session.get(QuestionnaireResponse, response_id)
    if response is None or response.user_id != current_user.id:
        raise not_found("questionnaire_response")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(response, key, value)
    await commit_or_409(session)
    await session.refresh(response)
    return response


@router.delete("/{response_id}", status_code=204)
async def delete_questionnaire_response(
    response_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    response = await session.get(QuestionnaireResponse, response_id)
    if response is None or response.user_id != current_user.id:
        raise not_found("questionnaire_response")
    await session.delete(response)
    await commit_or_409(session)
