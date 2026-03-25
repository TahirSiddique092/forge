import json
import hashlib
from fastapi import APIRouter, Header, HTTPException, Request
from app.core.queue import redis_client 
from app.models.worker import WorkerToken
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from sqlalchemy import text
from app.integrations.github.auth import get_installation_token
from app.integrations.github.checks import complete_check_run
from app.schemas.worker import UpdateStatusPayload, CreateStepPayload, FinishStepPayload
from app.core.limiter import limiter

router = APIRouter(prefix="/worker")

QUEUE_PREFIX = "ci_jobs"

@router.get("/next-job")
@limiter.limit("60/minute")
def get_next_job(request: Request, x_worker_token: str = Header(...)):
    
    project_id = get_project_id_from_token(x_worker_token)
    if not project_id:
        raise HTTPException(status_code=401, detail="Invalid worker token")

    queue_name = f"{QUEUE_PREFIX}:{project_id}"
    job_data = redis_client.lpop(queue_name)

    if not job_data:
        return {"job": None}  

    return {"job": json.loads(job_data)}

def get_project_id_from_token(token: str):
    db: Session = SessionLocal()

    hashed = hashlib.sha256(token.encode()).hexdigest()
    
    worker_token = db.query(WorkerToken).filter(
        WorkerToken.token == hashed
    ).first()
    
    if not worker_token:
        return None
    
    return worker_token.project_id

@router.patch("/runs/{run_id}/status")
def update_status(run_id: int, payload: UpdateStatusPayload, x_worker_token: str = Header(...)):
    
    project_id = get_project_id_from_token(x_worker_token)
    if not project_id:
        raise HTTPException(status_code=401, detail="Invalid worker token")
    
    installation_id = payload.installation_id
    repo = payload.repo
    check_run_id = payload.check_run_id
    success = payload.success
    
    db = SessionLocal()

    try:
        token = get_installation_token(installation_id)
       
        complete_check_run(
            token=token,
            repo=repo,
            check_run_id=check_run_id,
            conclusion="success" if success else "failure"
        )

        status = "success" if success else "failed"

    except Exception as e:
        try:
            token = get_installation_token(installation_id)
            
            complete_check_run(
                token=token,
                repo=repo,
                check_run_id=check_run_id,
                conclusion="failure",
                output={
                    "title": "forge CI failed",
                    "summary": str(e)
                }
            )
        except Exception as inner:
            return { "error": repr(inner) }

        status = "failed"

    db.execute(
        text("""
            UPDATE runs
            SET status=:status
            WHERE id=:id
        """),
        {
            "status": status,
            "id": run_id
        }
    )

    db.commit()
    
    return {"message": "Updated succesfully"}


@router.post("/runs/{run_id}/steps")
def create_step(run_id: int, payload: CreateStepPayload, x_worker_token: str = Header(...)):
    project_id = get_project_id_from_token(x_worker_token)
    if not project_id:
        raise HTTPException(status_code=401, detail="Invalid worker token")

    db = SessionLocal()
    step_id = db.execute(
        text("""
            INSERT INTO run_steps (run_id, name, status, step_order)
            VALUES (:run_id, :name, 'running',
                COALESCE((SELECT MAX(step_order) FROM run_steps WHERE run_id=:run_id), 0) + 1
            )
            RETURNING id
        """),
        {"run_id": run_id, "name": payload.name}
    ).scalar()
    db.commit()
    return {"step_id": step_id}

@router.patch("/runs/{run_id}/steps/{step_id}")
def finish_step(run_id: int, step_id: int, payload: FinishStepPayload, x_worker_token: str = Header(...)):
    project_id = get_project_id_from_token(x_worker_token)
    if not project_id:
        raise HTTPException(status_code=401, detail="Invalid worker token")

    db = SessionLocal()
    db.execute(
        text("""
            UPDATE run_steps
            SET status=:status, stdout=:stdout, stderr=:stderr, finished_at=now()
            WHERE id=:id
        """),
        {"id": step_id, "status": payload.status, "stdout": payload.stdout, "stderr": payload.stderr}
    )
    db.commit()
    return {"message": "Step updated"}