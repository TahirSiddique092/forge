import typer
import requests
from forge.config import load_config, save_config, get_auth_headers
import os

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def link(
    project_id: str,
    worker_token: str = typer.Option(..., "--worker-token", help="Worker token from dashboard")
):
    """
    Link this repository to a forge project
    """
    cfg = load_config()

    repo = cfg.get("repo")
    if not repo:
        typer.echo("Repo not initialized. Run `forge init` first.")
        raise typer.Exit(1)

    # SUCCESSFUL CALL: One single request including the Authorization headers
    try:
        r = requests.post(
            f"{BACKEND_URL}/projects/link",
            json={
                "project_id": project_id,
                "repo": repo
            },
            headers=get_auth_headers()
        )

        if r.status_code != 200:
            typer.echo(f"❌ Failed to link project: {r.status_code} - {r.text}")
            raise typer.Exit(1)

        # Save project_id locally
        cfg["project_id"] = project_id
        cfg["worker_token"] = worker_token
        save_config(cfg)

        typer.echo("Repo linked successfully")
        typer.echo(f"Project ID: {project_id}")
        
    except RuntimeError as e:
        typer.echo(f"❌ Auth Error: {e}")
        raise typer.Exit(1)