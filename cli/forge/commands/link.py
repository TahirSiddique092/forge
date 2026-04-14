import typer
import requests
import os
from forge.config import load_config, save_config, get_auth_headers
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-cpj5.onrender.com")


def link(
    project_id: str = typer.Argument(..., help="Project ID (proj_xxxxxxxx)"),
    worker_token: str = typer.Option(
        ...,
        "--worker-token",
        help="Worker token shown after [bold]forge create[/bold]",
    ),
):
    """
    Link this git repository to a Forge project.

    This tells Forge which project to associate with push events from this repo.
    Run once per project after [bold]forge create[/bold].
    """

    try:
        cfg = load_config()
    except Exception:
        ui.error("Not initialized. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    repo = cfg.get("repo")
    if not repo:
        ui.error("Repository not detected. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    try:
        headers = get_auth_headers()
    except RuntimeError as e:
        ui.error(str(e))
        raise typer.Exit(1)

    with ui.console.status("[dim]Linking repository...[/dim]", spinner="dots"):
        r = requests.post(
            f"{BACKEND_URL}/projects/link",
            json={"project_id": project_id, "repo": repo},
            headers=headers,
            timeout=10,
        )

    if r.status_code != 200:
        ui.error(f"Failed to link project ({r.status_code}): {r.text}")
        raise typer.Exit(1)

    cfg["project_id"]   = project_id
    cfg["worker_token"] = worker_token
    save_config(cfg)

    ui.success("Repository linked.")
    ui.blank()
    ui.label("Project ID",  project_id)
    ui.label("Repository",  repo)
    ui.blank()
    ui.console.print(f"    [yellow]IMPORTANT:[/yellow] To enable automatic CI webhooks, you must install the Forge GitHub App:\n    👉 [underline blue]https://github.com/apps/forge-ci-cd/installations/new[/underline blue]")
    ui.blank()
    ui.info("Next: run [bold]forge worker start[/bold] in a separate terminal to begin processing CI jobs.")