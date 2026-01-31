import typer
import requests
from forge.config import load_config, save_config

BACKEND_URL = "http://localhost:8000"

def link(project_id: str):
    """
    Link this repository to a forge project
    """
    cfg = load_config()

    repo = cfg.get("repo")
    if not repo:
        typer.echo("Repo not initialized. Run `forge init` first.")
        raise typer.Exit(1)

    # Call backend to bind repo → project
    r = requests.post(
        f"{BACKEND_URL}/projects/link",
        json={
            "project_id": project_id,
            "repo": repo
        }
    )

    if r.status_code != 200:
        typer.echo("❌ Failed to link project")
        raise typer.Exit(1)

    # Save project_id locally
    cfg["project_id"] = project_id
    save_config(cfg)

    typer.echo("🔗 Repo linked successfully")
    typer.echo(f"📦 Project ID: {project_id}")
