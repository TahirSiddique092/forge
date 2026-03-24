from app.routes import projects, webhooks, repos, worker, auth
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.models import *

app = FastAPI(title="Forge Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(webhooks.router)
app.include_router(repos.router)
app.include_router(worker.router)

@app.get("/ping")
def ping():
    return {"status": "ok"}