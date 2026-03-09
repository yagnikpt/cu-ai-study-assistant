from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

DBSession = Annotated[Session, Depends(get_db)]


def _get_current_user(request: Request, db: DBSession) -> User:
    """Wrapper to import auth lazily and avoid circular imports."""
    from app.auth import get_current_user

    return get_current_user(request, db)


CurrentUser = Annotated[User, Depends(_get_current_user)]
