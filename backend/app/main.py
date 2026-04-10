import os
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.routes import projects as projects_router
from app.routes import webhooks as webhooks_router
from app.routes import repos as repos_router
from app.routes import worker as worker_router
from app.routes import auth as auth_router
from app.routes import credentials as credentials_router
from app.core.database import Base, engine
from app.models import *
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.limiter import limiter
from app.core.queue import redis_client

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def keep_redis_alive():
    while True:
        try:
            redis_client.ping()
            logger.info("Redis ping OK")
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
        await asyncio.sleep(60 * 60 * 24)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    from sqlalchemy import text
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP + INTERVAL '30 days' NOT NULL;"))
        except Exception:
            pass

    Base.metadata.create_all(bind=engine)
    task = asyncio.create_task(keep_redis_alive())
    yield
    task.cancel()

app = FastAPI(title="Forge Backend", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(projects_router.router)
app.include_router(webhooks_router.router)
app.include_router(credentials_router.router)
app.include_router(repos_router.router)
app.include_router(worker_router.router)

@app.get("/ping")
def ping():
    return {"status": "ok"}