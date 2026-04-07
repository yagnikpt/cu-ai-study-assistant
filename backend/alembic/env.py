from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from alembic import context
from app.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


def _sync_alembic_url(database_url: str) -> str:
    """Convert async SQLAlchemy URLs to sync drivers for Alembic."""
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


# Set the sqlalchemy URL from our app config (forcing a sync driver for Alembic)
config.set_main_option("sqlalchemy.url", _sync_alembic_url(settings.database_url))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# We don't use autogenerate - migrations are raw SQL
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
