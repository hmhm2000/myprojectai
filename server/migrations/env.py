import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Folder server/ w sys.path, żeby importy działały niezależnie od katalogu startowego.
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import models  # noqa: E402,F401  (rejestruje wszystkie modele w Base.metadata)
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
        render_as_batch=True,  # SQLite nie wspiera większości ALTER TABLE
    )

    with context.begin_transaction():
        context.run_migrations()
