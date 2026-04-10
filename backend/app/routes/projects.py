from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
import uuid
import hashlib
from app.core.database import SessionLocal
from app.schemas.project import CreateProjectRequest
from app.core.database import SessionLocal
from app.models.project import Project
from app.models.repo_binding import RepoBinding
from app.models.run import Run
from app.models.run_step import RunStep
from app.models.worker import WorkerToken
from app.core.auth import get_current_user
from app.models.user import User
from app.core.limiter import limiter
from app.core.orchestrator import start_deployment_sequence

router = APIRouter(prefix="/projects")

class DeployPayload(BaseModel):
    component_envs: Optional[Dict[str, Dict[str, str]]] = {}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("")
@limiter.limit("20/minute")
def create_project(request: Request, data: CreateProjectRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = Project(
        name=data.name,
        project_id=f"proj_{uuid.uuid4().hex[:8]}",
        owner_id=current_user.id, 
        spec=data.spec.dict()
    )
    
    raw_token = f"wt_{uuid.uuid4().hex}"
    hashed = hashlib.sha256(raw_token.encode()).hexdigest()

    worker = WorkerToken(
        token=hashed,       
        project_id=project.project_id
    )
    
    db.add(project)
    db.add(worker)
    db.commit()
    db.refresh(project)
    db.refresh(worker)

    return {
        "project_details": {
            "project_id": project.project_id,
            "name": project.name,
            "spec": project.spec
        },
        "worker_details": {
            "worker_token": raw_token
        }
    }

@router.post("/link")
def link_project(
    payload: dict, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    project_id = payload.get("project_id")
    repo = payload.get("repo")

    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "").replace(".git", "")

    binding = db.query(RepoBinding).filter(RepoBinding.repo_full_name == repo).first()

    if binding:
        binding.project_id = project_id
    else:
        binding = RepoBinding(project_id=project_id, repo_full_name=repo)
        db.add(binding)

    db.commit()
    return {"status": "linked", "repo": repo, "project_id": project_id}


@router.get("/{project_id}/status")
def project_status(
    project_id: str, 
    current_user: User = Depends(get_current_user), # Fix 4: Added Auth
    db: Session = Depends(get_db)
):
    # Verify ownership
    project = db.query(Project).filter(Project.project_id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404)

    run = db.query(Run).filter(Run.project_id == project_id).order_by(Run.created_at.desc()).first()
    if not run:
        return {"status": "no runs yet"}

    return {
        "project": project_id,
        "run": {"commit": run.commit_sha, "status": run.status, "message": run.commit_message, "created_at": run.created_at}
    }


@router.get("/{project_id}/logs")
def project_logs(project_id: str, db: Session = Depends(get_db)):
    run = (
        db.query(Run)
        .filter(Run.project_id == project_id)
        .order_by(Run.created_at.desc())
        .first()
    )

    if not run:
        return {"status": "no runs yet"}

    steps = db.execute(
        text("""
            SELECT name, status, stdout, stderr, started_at, finished_at
            FROM run_steps
            WHERE run_id = :run_id
            ORDER BY id
        """),
        {"run_id": run.id}
    ).mappings().all()

    return {
        "project": project_id,
        "run_id": run.id,
        "status": run.status,
        "steps": steps,
        "created_at": run.created_at
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
    current_user: User = Depends(get_current_user)
):
    
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.owner_id == current_user.id  # ← security check
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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

@router.get("/{project_id}/runs/{index}/logs")
def run_logs(project_id: str, index: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if index < 1:
        raise HTTPException(status_code=400, detail="Index must be >= 1")

    run = (
        db.query(Run)
        .filter(Run.project_id == project_id)
        .order_by(Run.created_at.desc())
        .offset(index - 1)
        .limit(1)
        .first()
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = (
        db.query(RunStep)
        .filter(RunStep.run_id == run.id)
        .order_by(RunStep.step_order.asc())
        .all()
    )

    return {
        "project": project_id,
        "run_index": index,   
        "status": run.status,
        "commit": run.commit_sha,
        "message": run.commit_message,
        "created_at": run.created_at.isoformat(),
        "steps": [
            {
                "name": s.name,
                "order": s.step_order,
                "status": s.status,
                "started_at": s.started_at,
                "finished_at": s.finished_at,
                "stdout": s.stdout or "",
                "stderr": s.stderr or "",
            }
            for s in steps
        ]
    }
    
@router.post("/{project_id}/deploy")
async def deploy_project(
    project_id: str, 
    background_tasks: BackgroundTasks,
    payload: DeployPayload = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):

    project = db.query(Project).filter(Project.project_id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    last_run = db.query(Run).filter(Run.project_id == project_id).order_by(Run.created_at.desc()).first()

    if not last_run or last_run.status != "success":
        raise HTTPException(status_code=400, detail="Latest build/test failed. Fix your code first!")

    last_run.deploy_status = "initiated" 
    db.commit()

    envs = payload.component_envs if payload and payload.component_envs else {}
    background_tasks.add_task(start_deployment_sequence, project.id, last_run.id, envs)

    return {
        "message": "🚀 Deployment initiated!",
        "run_id": last_run.id,
        "status_command": f"forge deploy-status"
    }
    

@router.get("/{project_id}/deploy/status")
def get_deploy_status(
    project_id: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.project_id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

   
    run = db.query(Run).filter(Run.project_id == project_id).order_by(Run.created_at.desc()).first()
    
    if not run or not run.deploy_status:
        return {"status": "no_deployment_found"}

    return {
        "project_id": project_id,
        "deploy_status": run.deploy_status, 
        "components": run.component_results, 
        "updated_at": run.created_at 
    }