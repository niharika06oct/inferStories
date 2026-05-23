import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.auth import AuthUser, get_current_user
from app.database import get_db
from app.models import Claim, Scene, Story, ValidationIssue
from app.ai_description import generate_story_description
from app.claim_helpers import claim_to_out
from app.schemas import (
    ClaimOut,
    ClaimStatusUpdate,
    SceneCreate,
    SceneDetailOut,
    SceneOut,
    SceneSummaryOut,
    SceneUpdate,
    StoryCreate,
    StoryDescriptionOut,
    StoryListOut,
    StoryOut,
    StoryUpdate,
    ValidationIssueOut,
)
from app.scene_service import save_scene_with_extraction


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("SKIP_ALEMBIC_ON_STARTUP") != "1":
        print(
            "[startup] Running Alembic migrations "
            "(SKIP_ALEMBIC_ON_STARTUP=1 to skip)...",
            flush=True,
        )
        # Sync Alembic in a thread so --reload does not wedge the event loop.
        await asyncio.to_thread(_run_alembic_upgrade)
        print("[startup] Alembic migrations finished.", flush=True)
    print("[startup] API ready — accepting requests.", flush=True)
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


def _db_target_hint(url: str) -> str:
    """Safe one-line hint for logs (no password)."""
    if "@" in url:
        return url.split("@", 1)[-1]
    return url[:80]


def _run_alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    from app.database import DATABASE_URL

    print(f"[startup] Database target: {_db_target_hint(DATABASE_URL)}", flush=True)

    root = Path(__file__).resolve().parent.parent
    ini_path = root / "alembic.ini"
    cfg = Config(str(ini_path))
    command.upgrade(cfg, "head")


@app.get("/health")
def health():
    return {"status": "ok"}


def _story_for_user(db: Session, story_id: int, user: AuthUser) -> Story:
    story = db.get(Story, story_id)
    if not story or story.owner_user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


@app.get("/stories", response_model=list[StoryListOut])
def list_stories(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    rows = (
        db.query(
            Story,
            func.count(Scene.id).label("scene_count"),
        )
        .outerjoin(Scene, Scene.story_id == Story.id)
        .filter(Story.owner_user_id == user.user_id)
        .group_by(Story.id)
        .order_by(Story.created_at.desc())
        .all()
    )
    return [
        StoryListOut(
            id=story.id,
            title=story.title,
            description=story.description,
            created_at=story.created_at,
            scene_count=scene_count,
        )
        for story, scene_count in rows
    ]


@app.post("/stories", response_model=StoryOut)
def create_story(
    payload: StoryCreate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    story = Story(
        title=payload.title,
        description=payload.description,
        owner_user_id=user.user_id,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@app.get("/stories/{story_id}", response_model=StoryOut)
def get_story(
    story_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    return _story_for_user(db, story_id, user)


@app.patch("/stories/{story_id}", response_model=StoryOut)
def update_story(
    story_id: int,
    payload: StoryUpdate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    story = _story_for_user(db, story_id, user)
    if payload.title is None and payload.description is None:
        raise HTTPException(
            status_code=400, detail="Provide title and/or description to update"
        )
    if payload.title is not None:
        story.title = payload.title
    if payload.description is not None:
        story.description = payload.description.strip() or None
    db.commit()
    db.refresh(story)
    return story


@app.post(
    "/stories/{story_id}/generate-description",
    response_model=StoryDescriptionOut,
)
def generate_story_description_endpoint(
    story_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    story = _story_for_user(db, story_id, user)

    scenes = (
        db.query(Scene)
        .filter(Scene.story_id == story_id)
        .order_by(Scene.scene_number.asc())
        .all()
    )
    if not scenes:
        raise HTTPException(
            status_code=400,
            detail="Add at least one scene before generating a description",
        )

    scene_payload = [(s.scene_number, s.text) for s in scenes]
    description, source = generate_story_description(story.title, scene_payload)
    story.description = description
    db.commit()
    return StoryDescriptionOut(description=description, source=source)


@app.get("/stories/{story_id}/scenes", response_model=list[SceneSummaryOut])
def list_scenes(
    story_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _story_for_user(db, story_id, user)

    rows = (
        db.query(
            Scene,
            func.count(Claim.id).label("claim_count"),
        )
        .outerjoin(Claim, Claim.scene_id == Scene.id)
        .filter(Scene.story_id == story_id)
        .group_by(Scene.id)
        .order_by(Scene.scene_number.asc())
        .all()
    )
    return [
        SceneSummaryOut(
            id=scene.id,
            story_id=scene.story_id,
            scene_number=scene.scene_number,
            text=scene.text,
            created_at=scene.created_at,
            claim_count=claim_count,
        )
        for scene, claim_count in rows
    ]


@app.get("/stories/{story_id}/scenes/{scene_id}", response_model=SceneDetailOut)
def get_scene(
    story_id: int,
    scene_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _story_for_user(db, story_id, user)
    scene = (
        db.query(Scene)
        .options(joinedload(Scene.claims))
        .filter(Scene.id == scene_id, Scene.story_id == story_id)
        .first()
    )
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return SceneDetailOut(
        id=scene.id,
        story_id=scene.story_id,
        scene_number=scene.scene_number,
        text=scene.text,
        created_at=scene.created_at,
        claims=[claim_to_out(c) for c in scene.claims],
    )


@app.patch("/stories/{story_id}/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    story_id: int,
    scene_id: int,
    payload: SceneUpdate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _story_for_user(db, story_id, user)
    scene = (
        db.query(Scene)
        .filter(Scene.id == scene_id, Scene.story_id == story_id)
        .first()
    )
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    scene.scene_number = payload.scene_number
    scene.text = payload.text

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Scene number already exists for this story",
        ) from None

    if not payload.run_extraction:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Constraint violation while saving scene",
            ) from None
        db.refresh(scene)
        return SceneOut(
            id=scene.id,
            story_id=scene.story_id,
            scene_number=scene.scene_number,
            text=scene.text,
            issues=[],
            extraction=None,
        )

    _, extraction = save_scene_with_extraction(
        db, scene, payload.claims, run_extraction=True
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Constraint violation while saving scene or claims",
        ) from None
    db.refresh(scene)
    return SceneOut(
        id=scene.id,
        story_id=scene.story_id,
        scene_number=scene.scene_number,
        text=scene.text,
        extraction=extraction,
    )


@app.post("/stories/{story_id}/scenes", response_model=SceneOut)
def add_scene(
    story_id: int,
    payload: SceneCreate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _story_for_user(db, story_id, user)

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

    _, extraction = save_scene_with_extraction(
        db, scene, payload.claims, run_extraction=True
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Constraint violation while saving scene or claims",
        ) from None
    db.refresh(scene)
    return SceneOut(
        id=scene.id,
        story_id=scene.story_id,
        scene_number=scene.scene_number,
        text=scene.text,
        extraction=extraction,
    )


@app.patch(
    "/stories/{story_id}/scenes/{scene_id}/claims/{claim_id}",
    response_model=ClaimOut,
)
def update_claim_status(
    story_id: int,
    scene_id: int,
    claim_id: int,
    payload: ClaimStatusUpdate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _story_for_user(db, story_id, user)
    claim = (
        db.query(Claim)
        .filter(
            Claim.id == claim_id,
            Claim.scene_id == scene_id,
            Claim.story_id == story_id,
        )
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim.status = payload.status
    if payload.claim_text is not None:
        claim.claim_text = payload.claim_text.strip()
    if payload.subject is not None:
        claim.subject = payload.subject.strip()
    if payload.target is not None:
        claim.claim_object = payload.target.strip()

    scene = db.get(Scene, scene_id)
    if scene:
        db.query(ValidationIssue).filter(ValidationIssue.scene_id == scene.id).delete(
            synchronize_session=False
        )
        scene_claims = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        from app.validation import validate_scene_claims

        validate_scene_claims(db, scene, scene_claims)

    db.commit()
    db.refresh(claim)
    return claim_to_out(claim)


@app.post("/stories/{story_id}/validate", response_model=list[ValidationIssueOut])
def validate_story(
    story_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _story_for_user(db, story_id, user)

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
