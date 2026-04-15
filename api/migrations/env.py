import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import models.assignment  # noqa: F401
import models.flashcard_log  # noqa: F401
import models.flashcard_set  # noqa: F401
import models.grammar_rule  # noqa: F401
import models.learner_profile  # noqa: F401
import models.processed_image  # noqa: F401
import models.source  # noqa: F401
import models.submission  # noqa: F401
import models.vocabulary_item  # noqa: F401
from config import settings
from db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url, target_metadata=target_metadata, literal_column_name=True
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
