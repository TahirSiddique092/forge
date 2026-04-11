import os
import secrets
import requests
from fastapi import APIRouter, HTTPException, Header, Request, Depends
from fastapi.responses import HTMLResponse
from app.core.queue import redis_client
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DBSession
from app.core.database import SessionLocal
from app.models.user import User
from app.models.session import Session
from app.core.limiter import limiter
from datetime import datetime, timedelta, timezone



router = APIRouter(prefix="/auth")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/github")
@limiter.limit("10/minute")
def github_login(request: Request, auth_code: str = None):
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&scope=read:user"
    )
    if auth_code:
        url += f"&state={auth_code}"
    return RedirectResponse(url)


@router.get("/callback")
@limiter.limit("10/minute")
def github_callback(request: Request, code: str, state: str = None, db: Session = Depends(get_db)):
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
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        user = User(github_id=github_id, username=username)
        db.add(user)
        db.commit()
        db.refresh(user)

    # 4. Create session token
    session_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    session = Session(token=session_token, user_id=user.id, expires_at=expires_at)
    db.add(session)
    db.commit()

    if state:
        redis_client.set(f"auth_code:{state}", session_token, ex=300)

    html_content = """
    <html>
        <head>
            <style>
                body {
                    margin: 0;
                    height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background-color: #1c1c1c;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    color: #e0e0e0;
                }
                .wrapper {
                    text-align: center;
                }
                h1 { margin-top: 0; font-weight: 800; font-size: 42px; color: #2ecc71; margin-bottom: 16px; letter-spacing: -0.5px; }
                h2 { margin-top: 0; font-weight: 500; font-size: 20px; color: #ffffff; margin-bottom: 8px; }
                p { margin-bottom: 0; color: #999; font-size: 15px; }
            </style>
        </head>
        <body>
            <div class="wrapper">
                <h1>Forge</h1>
                <h2>Authentication Successful</h2>
                <p>You can now close this tab and return to your terminal.</p>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/poll")
def poll_auth(auth_code: str):
    token = redis_client.get(f"auth_code:{auth_code}")
    if token:
        redis_client.delete(f"auth_code:{auth_code}")
        return {"status": "success", "session_token": token}
    return {"status": "pending"}


@router.get("/me")
def get_me(authorization: str = Header(...), db: Session = Depends(get_db)): 
    token = authorization.replace("Bearer ", "")
    
    session = db.query(Session).filter(Session.token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == session.user_id).first()
    return {"id": user.id, "username": user.username}