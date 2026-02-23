from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_current_user(request: Request, db: DBSession) -> User:
    """Wrapper to import auth lazily and avoid circular imports."""
    from app.auth import get_current_user

    return await get_current_user(request, db)


CurrentUser = Annotated[User, Depends(_get_current_user)]
