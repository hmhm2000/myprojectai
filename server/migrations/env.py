import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Put server/ on sys.path so imports work regardless of the working directory.
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import models  # noqa: E402,F401  (registers all models in Base.metadata)
from config import settings  # noqa: E402
from database.db import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
fileConfig(config.config_file_name)

connectable = engine_from_config(
    config.get_section(config.config_ini_section, {}),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
)

with connectable.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,  # SQLite does not support most ALTER TABLE operations
    )

    with context.begin_transaction():
        context.run_migrations()
