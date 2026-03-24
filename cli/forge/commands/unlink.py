import typer
import requests
from forge.config import load_config, save_config
import os

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "http://localhost:8000")

def unlink():
    """
    Unlink this repository from forge
    """
    cfg = load_config()

    project_id = cfg.get("project_id")
    repo = cfg.get("repo")

    if not project_id or not repo:
        typer.echo("❌ Not linked")
        raise typer.Exit(1)

    requests.post(
        f"{BACKEND_URL}/projects/unlink",
        json={"project_id": project_id, "repo": repo}
    )

    cfg.pop("project_id", None)
    save_config(cfg)

    typer.echo("🔓 Repo unlinked successfully")
