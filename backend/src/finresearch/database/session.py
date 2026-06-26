from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from finresearch.settings import get_settings
from finresearch.database.models import Base

_INIT_LOCK = Lock()
_INITIALIZED_URLS: set[str] = set()


def database_url() -> str:
    settings = get_settings()
    return settings.database_url


@lru_cache(maxsize=8)
def build_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def init_db() -> None:
    url = database_url()
    if not _should_auto_create(url):
        return
    if url in _INITIALIZED_URLS:
        return
    with _INIT_LOCK:
        if url in _INITIALIZED_URLS:
            return
        engine = build_engine(url)
        Base.metadata.create_all(bind=engine)
        _INITIALIZED_URLS.add(url)


def _should_auto_create(url: str) -> bool:
    import os

    if "PYTEST_CURRENT_TEST" in os.environ:
        return True
    if os.getenv("FINRESEARCH_AUTO_CREATE_TABLES", "").lower() == "true":
        return True
    return url.startswith("sqlite")


def get_library_path() -> Path:
    return get_settings().sqlite_path


def get_session() -> Iterator[Session]:
    init_db()
    engine = build_engine(database_url())
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with session_local() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    init_db()
    engine = build_engine(database_url())
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with session_local() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
