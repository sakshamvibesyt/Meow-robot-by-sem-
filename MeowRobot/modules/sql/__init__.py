#
# Copyright (C) 2021-2022 by TheAloneteam@Github.
# MeowRobot SQL database setup.
#

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from MeowRobot import DB_URI, LOGGER as log

if not DB_URI:
    raise RuntimeError(
        "DATABASE_URL is missing. Set DATABASE_URL to your Render PostgreSQL Internal Database URL."
    )

if DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql://", 1)

BASE = declarative_base()

if DB_URI.startswith("sqlite"):
    engine = create_engine(DB_URI)
else:
    engine = create_engine(DB_URI, client_encoding="utf8", pool_pre_ping=True)

SESSION = scoped_session(sessionmaker(bind=engine, autoflush=False))


def initialize_tables() -> None:
    """
    Import every SQL model before create_all so every model is registered
    in BASE.metadata. Calling create_all during package import was too early:
    msg_delete and other tables were not registered yet.
    """
    import importlib
    import pkgutil

    package_name = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{package_name}.{module_info.name}")

    log.info("[PostgreSQL] Creating/checking database tables...")
    BASE.metadata.create_all(bind=engine)
    log.info("[PostgreSQL] Database tables are ready.")


def start() -> tuple[scoped_session, Any]:
    # Compatibility with older code that expects start() to return both.
    return SESSION, engine
