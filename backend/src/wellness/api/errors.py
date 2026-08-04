from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def commit_or_409(session: AsyncSession) -> None:
    """Commit the session, translating constraint violations into 409s.

    Covers both unique violations (email, account_number, ...) and any other
    integrity constraint (FK, CHECK) a smoke-test client might trip.
    """
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc.orig)) from exc


def not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{resource} not found")
