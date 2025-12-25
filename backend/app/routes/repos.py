from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.repo_binding import RepoBinding
from app.models.project import Project

router = APIRouter()

class RepoBindRequest(BaseModel):
    repo: str
    project_id: str

@router.post("/repos/bind")
def bind_repo(data: RepoBindRequest):
    db: Session = SessionLocal()

    project = db.query(Project).filter(
        Project.project_id == data.project_id
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
