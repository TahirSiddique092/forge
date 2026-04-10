import typer
import requests
import os
from forge.config import load_config, save_config
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")


def create(name: str = typer.Argument(..., help="Project name")):
    """
    Create a new Forge project and link this directory to it.

    Creates a project with a standard backend (Render) and frontend (Vercel)
    component spec. To use a custom spec, create the project via the dashboard.
    """

    try:
        cfg = load_config()
    except Exception:
        cfg = {}

    session_token = cfg.get("session_token")
    if not session_token:
        ui.error("Not authenticated. Run [bold]forge login[/bold] first.")
        raise typer.Exit(1)

    payload = {
        "name": name,
        "spec": {
            "components": [
                {
                    "name": "backend",
                    "platform": "render",
                    "root_dir": "backend",
                    "runtime": "python",
                    "install_command": "pip install -r requirements.txt",
                    "build_command": "uvicorn app.main:app --host 0.0.0.0 --port 10000",
                    "test_command": None,
                    "env_vars": {},
                },
                {
                    "name": "frontend",
                    "platform": "vercel",
                    "root_dir": "frontend",
                    "runtime": "node",
                    "install_command": "npm install",
                    "build_command": "npm run build",
                    "test_command": None,
                    "env_vars": {},
                },
            ]
        },
    }

    with ui.console.status("[dim]Creating project...[/dim]", spinner="dots"):
        r = requests.post(
            f"{BACKEND_URL}/projects",
            json=payload,
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=15,
        )

    if r.status_code != 200:
        ui.error(f"Failed to create project: {r.text}")
        raise typer.Exit(1)

    data       = r.json()
    proj_id    = data["project_details"]["project_id"]
    worker_tok = data["worker_details"]["worker_token"]

    cfg["project_id"]   = proj_id
    cfg["worker_token"] = worker_tok
    save_config(cfg)

    ui.success(f"Project [bold]{name}[/bold] created.")
    ui.blank()
    ui.label("Project ID",    proj_id)
    ui.label("Worker token",  worker_tok)
    ui.blank()
    ui.info("Next steps:")
    ui.console.print("    1. [bold]forge set-cred render[/bold]   — add your Render API key")
    ui.console.print("    2. [bold]forge set-cred vercel[/bold]   — add your Vercel token")
    ui.console.print("    3. [bold]forge link[/bold]              — link this repo to the project")