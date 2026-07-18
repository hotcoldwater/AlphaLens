import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, pool

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.api.app.core.database import database_path, database_url  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy ORM models exist in this codebase (raw SQL / sqlite3 / psycopg
# only, see services/api/app/core/database.py), so there is no MetaData to
# autogenerate against. Revisions are written by hand.
target_metadata = None


def _resolve_sqlalchemy_url() -> str:
    """Reuse the app's own DATABASE_URL / ALPHALENS_DATABASE_PATH resolution
    so `alembic upgrade head` always targets whatever database the API
    process itself would connect to (Neon in production, a local SQLite
    file in development)."""
    postgres_url = database_url()
    if postgres_url:
        # Neon/Render supply postgres:// or postgresql://; SQLAlchemy needs an
        # explicit driver so it loads the psycopg3 dialect already installed
        # for the app rather than trying (and failing) to import psycopg2.
        if postgres_url.startswith("postgresql+"):
            return postgres_url
        if postgres_url.startswith("postgresql://"):
            return postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if postgres_url.startswith("postgres://"):
            return postgres_url.replace("postgres://", "postgresql+psycopg://", 1)
        return postgres_url
    return f"sqlite:///{database_path()}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=_resolve_sqlalchemy_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(_resolve_sqlalchemy_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
