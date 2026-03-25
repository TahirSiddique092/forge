import os
import secrets
import requests
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DBSession
from app.core.database import SessionLocal
from app.models.user import User
from app.models.session import Session
from app.main import limiter

router = APIRouter(prefix="/auth")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@router.get("/github")
@limiter.limit("10/minute")
def github_login(request: Request):
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&scope=read:user"
    )
    return RedirectResponse(url)


@router.get("/callback")
@limiter.limit("10/minute")
def github_callback(request: Request, code: str):
    # 1. exchange code for github access token
    res = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        json={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
        },
    )
    res.raise_for_status()
    github_token = res.json().get("access_token")

    if not github_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth failed")

    # 2. get github user info
    user_res = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {github_token}"},
    )
    user_res.raise_for_status()
    github_user = user_res.json()

    github_id = str(github_user["id"])
    username = github_user["login"]

    # 3. find or create user in db
    db: DBSession = SessionLocal()

    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        user = User(github_id=github_id, username=username)
        db.add(user)
        db.commit()
        db.refresh(user)

    # 4. create session token
    session_token = secrets.token_hex(32)
    session = Session(token=session_token, user_id=user.id)
    db.add(session)
    db.commit()

    # 5. redirect to frontend with token
    return RedirectResponse(
        f"{FRONTEND_URL}/auth/callback?token={session_token}"
    )


@router.get("/me")
def get_me(authorization: str = Header(...)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    db: DBSession = SessionLocal()
    
    session = db.query(Session).filter(Session.token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == session.user_id).first()
    return {"id": user.id, "username": user.username}