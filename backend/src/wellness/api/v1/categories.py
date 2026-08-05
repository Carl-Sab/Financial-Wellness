# Read-only: categories are reference data seeded by the migration, not
# written through the API.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import not_found
from wellness.db import get_session
from wellness.models import Category
from wellness.schemas.categories import CategoryRead

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[Category]:
    result = await session.execute(
        select(Category).order_by(Category.code).limit(pagination.limit).offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{code}", response_model=CategoryRead)
async def get_category(code: str, session: AsyncSession = Depends(get_session)) -> Category:
    category = await session.get(Category, code)
    if category is None:
        raise not_found("category")
    return category
