"""Alembic environment — synchronous migrations, async runtime URL supported."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Import all models so Alembic can detect schema changes automatically
import core.models  # noqa: F401
import core.models_auth  # noqa: F401
from alembic import context
from core.config import get_settings as _get_settings
from core.database import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_settings = _get_settings()
# Alembic is intentionally synchronous. The application keeps asyncpg at
# runtime; migrations use psycopg so the canonical multi-statement bootstrap
# SQL executes portably, including on the Windows Proactor event loop.
config.set_main_option(
    "sqlalchemy.url",
    _settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
