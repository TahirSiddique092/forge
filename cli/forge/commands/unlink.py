import typer
import requests
import os
from forge.config import load_config, save_config, get_auth_headers
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-cpj5.onrender.com")


def unlink():
    """Remove the link between this repository and its Forge project."""

    try:
        cfg = load_config()
    except Exception:
        ui.error("Not initialized. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    project_id = cfg.get("project_id")
    repo       = cfg.get("repo")

    if not project_id or not repo:
        ui.warn("This directory is not linked to any project.")
        raise typer.Exit(0)

    try:
        headers = get_auth_headers()
    except RuntimeError as e:
        ui.error(str(e))
        raise typer.Exit(1)

    with ui.console.status("[dim]Unlinking repository...[/dim]", spinner="dots"):
        requests.post(
            f"{BACKEND_URL}/projects/unlink",
            json={"project_id": project_id, "repo": repo},
            headers=headers,
            timeout=10,
        )

    cfg.pop("project_id", None)
    save_config(cfg)

    ui.success("Repository unlinked.")
    ui.label("Removed link", f"{repo}  →  {project_id}")