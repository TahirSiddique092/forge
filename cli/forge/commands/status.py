import typer
import requests
import os
from forge.config import load_config, get_auth_headers
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-cpj5.onrender.com")


def status(
    all: bool = typer.Option(False, "--all", "-a", help="Show all runs"),
    limit: int = typer.Option(None,  "--limit", "-n", help="Show last N runs"),
):
    """
    Show CI run status for the current project.

    By default shows the most recent run. Use --all or --limit to see more.

    \b
    Examples:
      forge status
      forge status --limit 10
      forge status --all
    """

    try:
        cfg = load_config()
    except Exception:
        ui.error("Not initialized. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    project_id = cfg.get("project_id")
    if not project_id:
        ui.error("Not linked to any project. Run [bold]forge link[/bold] first.")
        raise typer.Exit(1)

    repo = cfg.get("repo", "")

    if limit is not None:
        url = f"{BACKEND_URL}/projects/{project_id}/runs?limit={limit}"
    elif all:
        url = f"{BACKEND_URL}/projects/{project_id}/runs"
    else:
        url = f"{BACKEND_URL}/projects/{project_id}/status"

    try:
        r = requests.get(url, headers=get_auth_headers(), timeout=10)
    except requests.RequestException as e:
        ui.error(f"Request failed: {e}")
        raise typer.Exit(1)

    if r.status_code != 200:
        ui.error(f"Could not fetch status ({r.status_code}).")
        raise typer.Exit(1)

    data = r.json()

    # ── Header ──────────────────────────────────────────────────────────────
    ui.blank()
    ui.label("Project",    project_id)
    if repo:
        ui.label("Repository", repo)
    ui.blank()

    # ── Single (latest) run ─────────────────────────────────────────────────
    if limit is None and not all:
        run = data.get("run")
        if not run:
            ui.warn("No CI runs found for this project.")
            return

        ui.console.rule("[dim]Last Run[/dim]", style="dim")
        ui.label("Commit",  (run.get("commit") or "")[:7])
        ui.label("Message", run.get("message") or "(no message)")
        ui.label("Status",  "")
        # Print badge inline after the status label
        badge = ui.status_badge(run.get("status", ""))
        ui.console.print(f"  {'':14}", end="")
        ui.console.print(badge)
        ui.label("Created", _fmt(run.get("created_at", "")))
        ui.blank()
        return

    # ── Multiple runs ────────────────────────────────────────────────────────
    runs = data.get("runs", [])
    if not runs:
        ui.warn("No CI runs found for this project.")
        return

    title = "All Runs" if all else f"Last {len(runs)} Runs"
    ui.console.rule(f"[dim]{title}[/dim]", style="dim")
    ui.blank()
    ui.runs_table(runs)


def _fmt(ts: str) -> str:
    if not ts:
        return "—"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)[:16]