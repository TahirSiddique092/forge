import hmac
import hashlib
import os
import time
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.project import Project
from app.models.run import Run
from app.models.repo_binding import RepoBinding
from app.core.queue import enqueue_ci_job
from app.integrations.github.auth import get_installation_token
from app.integrations.github.checks import create_check_run
from sqlalchemy import text


router = APIRouter()


GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_github_signature(payload: bytes, signature: str):
    mac = hmac.new(
        GITHUB_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    )
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("/webhooks/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    
    if not signature or not verify_github_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = request.headers.get("X-GitHub-Event")

    if event != "push":
        return {"status": "ignored"}

    repo = payload["repository"]["full_name"]
    commit_sha = payload["after"]
    commit_msg = payload["head_commit"]["message"].split("\n")[0]

    installation_id = payload["installation"]["id"]

    binding = db.query(RepoBinding).filter(RepoBinding.repo_full_name == repo).first()
    if not binding:
        return {"status": "repo not linked"}

    token = get_installation_token(installation_id)

    check_run_id = create_check_run(
        token=token,
        repo=repo,
        sha=commit_sha
    )

    run = Run(
        project_id=binding.project_id,
        commit_sha=commit_sha,
        commit_message=commit_msg,
        status="queued",
        check_run_id=check_run_id,
        installation_id=installation_id
    )


    db.add(run)
    db.commit()
    db.refresh(run)
    
    project = db.query(Project).filter(
        Project.project_id == binding.project_id
    ).first()

    enqueue_ci_job({
        "run_id": run.id,
        "project_id": binding.project_id,
        "repo": repo,     
        "commit": commit_sha,
        "check_run_id": check_run_id,
        "installation_id": installation_id,
        "spec": project.spec
    })


    print(f"🚀 CI run queued: run_id={run.id}")

    return {"status": "queued"}
