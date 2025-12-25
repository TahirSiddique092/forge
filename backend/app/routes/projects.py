from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from app.core.database import SessionLocal
from app.schemas.project import CreateProjectRequest
from app.core.database import SessionLocal
from app.models.project import Project
from app.models.repo_binding import RepoBinding
from app.models.run import Run

router = APIRouter(prefix="/projects")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("")
def create_project(data: CreateProjectRequest, db: Session = Depends(get_db)):
    project = Project(
        name=data.name,
        project_id=f"proj_{uuid.uuid4().hex[:8]}",
        owner_id=1,  # TEMP (auth later)
        spec=data.spec.dict()
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return {
        "project_id": project.project_id,
        "name": project.name,
        "spec": project.spec
    }

@router.post("/link")
def link_project(payload: dict):
    project_id = payload.get("project_id")
    repo = payload.get("repo")

    if not project_id or not repo:
        raise HTTPException(status_code=400, detail="Missing data")

    # Normalize repo URL → owner/repo
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "").replace(".git", "")

    db: Session = SessionLocal()

    # 1️⃣ Ensure project exists
    project = db.query(Project).filter(
        Project.project_id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2️⃣ Upsert repo binding
    binding = db.query(RepoBinding).filter(
        RepoBinding.repo_full_name == repo
    ).first()

    if binding:
        binding.project_id = project_id
    else:
        binding = RepoBinding(
            id=str(uuid.uuid4()),
            project_id=project_id,
            repo_full_name=repo
        )
        db.add(binding)

    db.commit()

    return {"status": "linked", "repo": repo, "project_id": project_id}


@router.get("/{project_id}/status")
def project_status(project_id: str, db: Session = Depends(get_db)):
    run = (
        db.query(Run)
        .filter(Run.project_id == project_id)
        .order_by(Run.created_at.desc())
        .first()
    )

    if not run:
        return {"status": "no runs yet"}

    return {
        "project": project_id,
        "run": {
            "commit": run.commit_sha,
            "status": run.status,
            "message": run.commit_message,
            "created_at": run.created_at
        }
    }


@router.get("/{project_id}/logs")
def project_logs(project_id: str):
    db = SessionLocal()

    run = (
        db.query(Run)
        .filter(Run.project_id == project_id)
        .order_by(Run.created_at.desc())
        .first()
    )

    if not run:
        return {"status": "no runs yet"}

    return {
        "project": project_id,
        "run_id": run.id,
        "status": run.status,
        "stdout": run.stdout or "",
        "stderr": run.stderr or "",
        "created_at": run.created_at.isoformat()
    }

@router.post("/unlink")
def unlink_repo(payload: dict):
    db = SessionLocal()

    project_id = payload["project_id"]
    repo = payload["repo"]

    binding = db.query(RepoBinding).filter(
        RepoBinding.project_id == project_id,
        RepoBinding.repo_full_name == repo
    ).first()

    if not binding:
        return {"status": "not linked"}

    db.delete(binding)
    db.commit()

    return {"status": "unlinked"}

@router.get("/{project_id}/runs")
def project_runs(
    project_id: str,
    limit: int | None = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(Run)
        .filter(Run.project_id == project_id)
        .order_by(Run.created_at.desc())
    )

    if limit:
        q = q.limit(limit)

    runs = q.all()

    return {
        "project": project_id,
        "runs": [
            {
                "commit": r.commit_sha,
                "message": r.commit_message,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in runs
        ],
    }
