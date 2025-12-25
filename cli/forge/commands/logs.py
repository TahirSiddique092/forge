import typer
import requests
from forge.config import load_config

BACKEND_URL = "http://localhost:8000"

def logs():
    """
    Show logs of the latest CI run
    """
    cfg = load_config()
    project_id = cfg.get("project_id")

    if not project_id:
        typer.echo("❌ Not linked to any project")
        raise typer.Exit(1)

    r = requests.get(
        f"{BACKEND_URL}/projects/{project_id}/logs"
    )

    if r.status_code != 200:
        typer.echo("❌ Failed to fetch logs")
        raise typer.Exit(1)

    data = r.json()

    if data.get("status") == "no runs yet":
        typer.echo("No CI runs yet")
        return

    typer.echo(f"\n📦 Project: {project_id}")
    typer.echo(f"🧪 Run ID: {data['run_id']}")
    typer.echo(f"📅 Time: {data['created_at']}")
    typer.echo("\n📤 STDOUT:\n")
    typer.echo(data["stdout"] or "(empty)")
    typer.echo("\n📥 STDERR:\n")
    typer.echo(data["stderr"] or "(empty)")
