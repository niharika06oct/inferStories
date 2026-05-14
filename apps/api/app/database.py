import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.is_file():
    from dotenv import load_dotenv

    load_dotenv(_env_file)

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. In apps/api, run: cp env.example .env — then edit .env so "
        "DATABASE_URL=... is a real line (not commented with #) and matches your Postgres user "
        "and password (see scripts/reset_local_postgres.sql).",
    )

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
