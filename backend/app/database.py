from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _sync_database_url(database_url: str) -> str:
    url = make_url(database_url)

    driver_map = {
        "postgresql+asyncpg": "postgresql+psycopg2",
        "postgresql+psycopg": "postgresql+psycopg2",
        "sqlite+aiosqlite": "sqlite",
    }
    sync_driver = driver_map.get(url.drivername)
    if sync_driver:
        url = url.set(drivername=sync_driver)

    return url.render_as_string(hide_password=False)


engine = create_engine(
    _sync_database_url(settings.database_url),
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

session_factory = sessionmaker(
    engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session]:
    with session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
