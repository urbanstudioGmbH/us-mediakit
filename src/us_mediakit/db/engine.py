"""SQLAlchemy Engine/Session, DB-URL-Konfiguration (SQLite/MariaDB/PostgreSQL)."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///us_mediakit.db"


def get_database_url() -> str:
    return os.environ.get("USMEDIAKIT_DB", DEFAULT_DATABASE_URL)


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Legt alle Tabellen an, falls sie nicht existieren. Für Produktivbetrieb Alembic
    (`db/migrations/`) verwenden, nicht diese Funktion — sie kennt keine Migrationen,
    nur den aktuellen Modellstand."""
    from us_mediakit.db.models import Base

    Base.metadata.create_all(engine)
