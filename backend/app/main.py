from fastapi import FastAPI
from app.routes import projects, webhooks, repos, worker


app = FastAPI(title="Forge Backend")

app.include_router(projects.router)
app.include_router(webhooks.router)
app.include_router(repos.router)
app.include_router(worker.router)

@app.get("/")
def health():
    return {"status": "running"}
