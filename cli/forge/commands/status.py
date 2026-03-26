import typer
import requests
from datetime import datetime
from forge.config import load_config, get_auth_headers
import os

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def fmt_time(ts: str):
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M")

def status(
    all: bool = typer.Option(
        False, "--all", help="Show all runs"
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-n", help="Show last N runs"
    ),
):
    cfg = load_config()
    project_id = cfg["project_id"]
    repo = cfg.get("repo", "")

    # ---------------- URL SELECTION ----------------
    if limit is not None:
        url = f"{BACKEND_URL}/projects/{project_id}/runs?limit={limit}"
    elif all:
        url = f"{BACKEND_URL}/projects/{project_id}/runs"
    else:
        url = f"{BACKEND_URL}/projects/{project_id}/status"

    r = requests.get(url, headers=get_auth_headers())
    if r.status_code != 200:
        typer.echo("Error: unable to fetch project status")
        raise typer.Exit(1)

    data = r.json()

    # ---------------- HEADER ----------------
    typer.echo("")
    typer.echo(f"Project     {project_id}")
    if repo:
        typer.echo(f"Repository  {repo}")
    typer.echo("")

    # ================= LAST RUN =================
    if limit is None and not all:
        run = data.get("run")
        if not run:
            typer.echo("No CI runs yet")
            return

        message = run.get("message") or "(no commit message)"

        typer.echo("Last Run")
        typer.echo("-" * 60)
        typer.echo(f"Commit      {run['commit'][:7]}   {message}")
        typer.echo(f"Status      {run['status']}")
        typer.echo(f"Created     {fmt_time(run['created_at'])}")
        return

    # ================= MULTIPLE RUNS =================
    runs = data.get("runs", [])

    if not runs:
        typer.echo("No CI runs yet")
        return

    title = (
        "All Runs"
        if all
        else f"Recent Runs (last {len(runs)})"
    )

    typer.echo(title)
    typer.echo("-" * 60)

    typer.echo(
        f"{'Commit':8} {'Status':8} {'Message':28} Created"
    )

    for run in runs:
        message = (run.get("message") or "(no message)")[:28]

        typer.echo(
            f"{run['commit'][:7]:8} "
            f"{run['status']:8} "
            f"{message:28} "
            f"{fmt_time(run['created_at'])}"
        )