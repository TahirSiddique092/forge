from fastapi import FastAPI
from app.models import user, project  
from app.routes import projects, webhooks, repos


app = FastAPI(title="MyCI Backend")

app.include_router(projects.router)
app.include_router(webhooks.router)
app.include_router(repos.router)

@app.get("/")
def health():
    return {"status": "running"}
