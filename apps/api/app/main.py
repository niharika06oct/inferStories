from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Claim, Scene, Story, ValidationIssue
from app.schemas import (
    SceneCreate,
    SceneOut,
    StoryCreate,
    StoryOut,
    ValidationIssueOut,
)
from app.validation import validate_scene_claims

app = FastAPI(title="Writers AI Memory API")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    db.flush()

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
    db.commit()
    db.refresh(scene)
    return scene


@app.post("/stories/{story_id}/validate", response_model=list[ValidationIssueOut])
def validate_story(story_id: int, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    issues = (
        db.query(ValidationIssue)
        .filter(ValidationIssue.story_id == story_id)
        .order_by(ValidationIssue.id.desc())
        .all()
    )
    return issues
