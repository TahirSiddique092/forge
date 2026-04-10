import typer
import requests
import os
from forge.config import load_config, get_auth_headers
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")


def logs(
    run: int = typer.Option(
        None,
        "--run", "-r",
        help="Index of the run to inspect (1 = latest, 2 = second latest, ...)",
    ),
):
    """
    Show step-by-step CI logs for a run.

    Defaults to the most recent run. Use --run to target a specific run
    by its position in the history (1 = latest).

    \b
    Examples:
      forge logs
      forge logs --run 2
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

    url = (
        f"{BACKEND_URL}/projects/{project_id}/runs/{run}/logs"
        if run
        else f"{BACKEND_URL}/projects/{project_id}/logs"
    )

    try:
        r = requests.get(url, headers=get_auth_headers(), timeout=10)
    except requests.RequestException as e:
        ui.error(f"Request failed: {e}")
        raise typer.Exit(1)

    if r.status_code != 200:
        ui.error(f"Could not fetch logs ({r.status_code}).")
        raise typer.Exit(1)

    data = r.json()

    if data.get("status") == "no runs yet":
        ui.warn("No CI runs found for this project.")
        return

    # ── Header ───────────────────────────────────────────────────────────────
    ui.blank()
    ui.label("Project",  project_id)
    ui.label("Run",      f"#{data.get('run_id', 'latest')}")
    ui.label("Commit",   (data.get("commit") or "")[:7])
    ui.label("Message",  data.get("message") or "(no message)")
    ui.console.print(f"  [dim]{'Status':<14}[/dim]", end="")
    ui.console.print(ui.status_badge(data.get("status", "")))
    ui.label("Created",  _fmt(data.get("created_at", "")))

    steps = data.get("steps", [])
    if not steps:
        ui.blank()
        ui.warn("No steps recorded for this run.")
        return

    # ── Step summary table ────────────────────────────────────────────────────
    ui.blank()
    ui.console.rule("[dim]Steps[/dim]", style="dim")
    ui.steps_table(steps)

    # ── Per-step output ───────────────────────────────────────────────────────
    has_output = any(s.get("stdout") or s.get("stderr") for s in steps)
    if has_output:
        ui.console.rule("[dim]Output[/dim]", style="dim")
        ui.render_step_logs(steps)

    ui.blank()


def _fmt(ts: str) -> str:
    if not ts:
        return "—"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)[:16]