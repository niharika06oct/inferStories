import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Claim, Scene, Story, ValidationIssue
from app.schemas import (
    SceneCreate,
    SceneOut,
    StoryCreate,
    StoryOut,
    ValidationIssueOut,
)
from app.validation import validate_scene_claims


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("SKIP_ALEMBIC_ON_STARTUP") != "1":
        print(
            "[startup] Running Alembic migrations "
            "(SKIP_ALEMBIC_ON_STARTUP=1 to skip)...",
            flush=True,
        )
        _run_alembic_upgrade()
        print("[startup] Alembic migrations finished.", flush=True)
    yield


app = FastAPI(title="Writers AI Memory API", lifespan=lifespan)


@app.exception_handler(SQLAlchemyError)
def _db_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Return JSON instead of a generic 500 so the UI can show a useful message."""
    orig = getattr(exc, "orig", None)
    hint = str(orig) if orig is not None else str(exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Database error. Check DATABASE_URL, Postgres is running, and the "
                "database exists (default name: writers_ai_memory — run createdb if needed). "
                f"Hint: {hint}"
            )
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    ini_path = root / "alembic.ini"
    cfg = Config(str(ini_path))
    command.upgrade(cfg, "head")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/stories", response_model=StoryOut)
def create_story(payload: StoryCreate, db: Session = Depends(get_db)):
    story = Story(title=payload.title, description=payload.description)
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@app.post("/stories/{story_id}/scenes", response_model=SceneOut)
def add_scene(story_id: int, payload: SceneCreate, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    scene = Scene(
        story_id=story_id,
        scene_number=payload.scene_number,
        text=payload.text,
    )
    db.add(scene)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Scene number already exists for this story",
        ) from None

    new_claims: list[Claim] = []
    for c in payload.claims:
        claim = Claim(
            story_id=story_id,
            scene_id=scene.id,
            subject=c.subject,
            predicate=c.predicate,
            claim_object=c.object,
            is_major_plotline=c.is_major_plotline,
        )
        db.add(claim)
        new_claims.append(claim)

    db.flush()
    validate_scene_claims(db, scene, new_claims)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Constraint violation while saving scene or claims",
        ) from None
    db.refresh(scene)
    return scene


@app.post("/stories/{story_id}/validate", response_model=list[ValidationIssueOut])
def validate_story(story_id: int, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    rows = (
        db.query(ValidationIssue)
        .options(joinedload(ValidationIssue.scene))
        .filter(ValidationIssue.story_id == story_id)
        .order_by(ValidationIssue.id.desc())
        .all()
    )
    return [
        ValidationIssueOut(
            id=i.id,
            story_id=i.story_id,
            scene_id=i.scene_id,
            scene_number=i.scene.scene_number,
            severity=i.severity,
            message=i.message,
            conflicting_claim_id=i.conflicting_claim_id,
            created_at=i.created_at,
        )
        for i in rows
    ]
