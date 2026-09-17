"""Engine / session management and schema bootstrap."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import get_settings
from src.database.models import Base

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


class DatabaseUnavailable(RuntimeError):
    """Raised when the configured database cannot be reached."""


def get_engine() -> Engine:
    global _engine, _SessionFactory
    if _engine is not None:
        return _engine

    settings = get_settings()
    kwargs = {"future": True, "pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    _engine = create_engine(settings.database_url, **kwargs)

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _fk_on(dbapi_connection, _):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_session_factory() -> sessionmaker:
    if _SessionFactory is None:
        get_engine()
    assert _SessionFactory is not None
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope. Rolls back on any exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(drop: bool = False) -> None:
    """Create the schema (and the pgvector extension when on PostgreSQL)."""
    engine = get_engine()
    settings = get_settings()
    try:
        if settings.is_postgres:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        if drop:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    except SQLAlchemyError as exc:  # pragma: no cover - environment dependent
        raise DatabaseUnavailable(
            f"Could not initialise the database at {_safe_url(settings.database_url)}: {exc}"
        ) from exc


def healthcheck() -> bool:
    """True when the database answers a trivial query."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:  # pragma: no cover - environment dependent
        logger.warning("Database healthcheck failed: %s", exc)
        return False


def _safe_url(url: str) -> str:
    """Strip credentials before a URL is shown to a user or written to a log."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    _, _, host = rest.partition("@")
    return f"{scheme}://***@{host}"


def describe_database() -> str:
    settings = get_settings()
    return f"{settings.database_flavor} — {_safe_url(settings.database_url)}"


def reset_engine() -> None:
    """Drop cached engine/session factory (tests switch databases at runtime)."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
