import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routes import projects, webhooks, repos, worker, auth
from app.core.database import Base, engine
from app.models import *
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.limiter import limiter
from app.core.queue import redis_client

async def keep_redis_alive():
    while True:
        try:
            redis_client.ping()
            print("Redis ping OK")
        except Exception as e:
            print(f"Redis ping failed: {e}")
        # ping every 24 hours
        await asyncio.sleep(60 * 60 * 24)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app = FastAPI(title="Forge Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(keep_redis_alive())

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(webhooks.router)
app.include_router(repos.router)
app.include_router(worker.router)

@app.get("/ping")
def ping():
    return {"status": "ok"}