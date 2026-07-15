from logging.config import fileConfig
from pathlib import Path
import sys

from sqlalchemy import create_engine, pool

from alembic import context

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.settings import Settings  # noqa: E402
import db.models  # noqa: E402, F401
from db.base import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def sync_url() -> str:
    url = Settings().database_url
    return url.replace("+asyncpg", "+psycopg2") if "+asyncpg" in url else url


def run_migrations_offline() -> None:
    url = sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(sync_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
