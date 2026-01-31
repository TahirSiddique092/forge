import typer
import requests
from forge.config import load_config

BACKEND_URL = "http://localhost:8000"

def logs(
    run: int | None = typer.Option(
        None, "--run", "-r", help="Show Nth latest run logs (1 = latest)"
    )
):
    cfg = load_config()
    project_id = cfg.get("project_id")

    if not project_id:
        typer.echo("❌ Not linked to any project. Run `forge link`.")
        raise typer.Exit(1)

    if run:
        url = f"{BACKEND_URL}/projects/{project_id}/runs/{run}/logs"
    else:
        url = f"{BACKEND_URL}/projects/{project_id}/logs"

    r = requests.get(url)
    if r.status_code != 200:
        typer.echo("❌ Failed to fetch logs")
        raise typer.Exit(1)

    data = r.json()

    typer.echo(f"\nProject  {project_id}")
    typer.echo(f"Run      #{data.get('run_id', 'latest')}")
    typer.echo(f"Status   {data.get('status', 'unknown')}")
    typer.echo("-" * 60)

    # 🔹 STEP-BASED LOGS (new runs)
    if "steps" in data:
        for step in data["steps"]:
            typer.echo(f"\n▶ {step['name']}")
            typer.echo(f"Status     {step['status']}")

            if step.get("duration"):
                typer.echo(f"Duration   {step['duration']} ms")

            if step.get("stdout"):
                typer.echo("\n--- stdout ---")
                typer.echo(step["stdout"].rstrip())

            if step.get("stderr"):
                typer.echo("\n--- stderr ---")
                typer.echo(step["stderr"].rstrip())

    # 🔹 FLAT LOGS (legacy runs)
    else:
        typer.echo("\n--- stdout ---")
        typer.echo((data.get("stdout") or "(empty)").rstrip())

        typer.echo("\n--- stderr ---")
        typer.echo((data.get("stderr") or "(empty)").rstrip())