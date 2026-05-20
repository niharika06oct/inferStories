import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.is_file():
    from dotenv import load_dotenv

    # Prefer apps/api/.env over inherited shell vars (e.g. auth-service DATABASE_URL).
    load_dotenv(_env_file, override=True)

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. In apps/api, run: cp env.example .env — then edit .env so "
        "DATABASE_URL=... is a real line (not commented with #) and matches your Postgres user "
        "and password (see scripts/reset_local_postgres.sql).",
    )

_connect_args: dict = {}
if DATABASE_URL.startswith("postgresql"):
    _connect_args["connect_timeout"] = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

_engine_kw: dict = {"echo": False}
if _connect_args:
    _engine_kw["connect_args"] = _connect_args
engine = create_engine(DATABASE_URL, **_engine_kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
