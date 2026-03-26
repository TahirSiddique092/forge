import typer
import requests
import os
import time
from forge.config import load_config

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def deploy_status():
    """
    Check the current status of your full-stack deployment.
    """
    cfg = load_config()
    project_id = cfg.get("project_id")
    token = cfg.get("session_token")

    if not project_id:
        typer.echo("❌ Not linked to a project.")
        raise typer.Exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BACKEND_URL}/projects/{project_id}/deploy/status", headers=headers)

    if r.status_code != 200:
        typer.echo("❌ Failed to fetch status.")
        raise typer.Exit(1)

    data = r.json()
    status = data.get("deploy_status", "unknown")
    components = data.get("components", {})

    typer.echo(f"\nProject ID: {project_id}")
    typer.echo(f"Current Phase: {status.upper()}")
    typer.echo("-" * 40)

    if status == "success":
        typer.echo("🎉 DEPLOYMENT COMPLETE!")
        for name, info in components.items():
            typer.echo(f"🔗 {name.capitalize()} URL: {info.get('url')}")
    elif "failed" in status:
        typer.echo(f"❌ Deployment Failed: {status}")
    else:
        typer.echo("⏳ Deployment is still in progress. Check back in a few seconds.")