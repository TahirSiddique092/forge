from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.repo_binding import RepoBinding
from app.models.project import Project
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()

class RepoBindRequest(BaseModel):
    repo: str
    project_id: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/repos/bind")
def bind_repo(data: RepoBindRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(
        Project.project_id == data.project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    binding = db.query(RepoBinding).filter(
        RepoBinding.repo_full_name == data.repo
    ).first()

    if binding:
        binding.project_id = data.project_id
    else:
        binding = RepoBinding(
            repo_full_name=data.repo,
            project_id=data.project_id
        )
        db.add(binding)

    db.commit()
    return {"status": "linked"}
