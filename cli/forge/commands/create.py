import typer
import requests
import os
from rich.prompt import Prompt
from forge.config import load_config, save_config
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-cpj5.onrender.com")


def create(name: str = typer.Argument(..., help="Project name")):
    """
    Create a new Forge project and link this directory to it.

    Creates a project with a standard backend (Railway) and frontend (Vercel)
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

    ui.blank()
    ui.header("Backend Configuration (Railway)")
    backend_choice = Prompt.ask(
        "Framework",
        choices=["fastapi", "flask", "express", "custom"],
        default="fastapi",
        console=ui.console
    )

    if backend_choice == "fastapi":
        b_runtime = "python"
        b_install = "pip install -r requirements.txt"
        b_build   = "uvicorn app.main:app --host 0.0.0.0 --port $PORT" 
        
    elif backend_choice == "flask":
        b_runtime = "python"
        b_install = "pip install -r requirements.txt"
        b_build   = "gunicorn app:app -b 0.0.0.0:$PORT" 
        
    elif backend_choice == "express":
        b_runtime = "node"
        b_install = "npm install"
        b_build   = "npm start" 
    else:
        b_runtime = Prompt.ask("  Runtime", choices=["python", "node"], default="python", console=ui.console)
        b_install = Prompt.ask("  Install Command", default="pip install -r requirements.txt", console=ui.console)
        b_build   = Prompt.ask("  Build/Start Command", default="uvicorn app.main:app --host 0.0.0.0 --port $PORT", console=ui.console)


    b_root = Prompt.ask("Root directory", default="backend", console=ui.console)

    ui.blank()
    ui.header("Frontend Configuration (Vercel)")
    frontend_choice = Prompt.ask(
        "Framework",
        choices=["nextjs", "vite", "custom"],
        default="nextjs",
        console=ui.console
    )

    if frontend_choice == "nextjs" or frontend_choice == "vite":
        f_runtime = "node"
        f_install = "npm install"
        f_build   = "npm run build"
    else:
        f_runtime = Prompt.ask("  Runtime", choices=["node", "python"], default="node", console=ui.console)
        f_install = Prompt.ask("  Install Command", default="npm install", console=ui.console)
        f_build   = Prompt.ask("  Build Command", default="npm run build", console=ui.console)

    f_root = Prompt.ask("Root directory", default="frontend", console=ui.console)
    ui.blank()

    payload = {
        "name": name,
        "spec": {
            "components": [
                {
                    "name": "backend",
                    "platform": "railway",
                    "root_dir": b_root,
                    "runtime": b_runtime,
                    "install_command": b_install,
                    "build_command": b_build,
                    "test_command": None,
                    "env_vars": {},
                },
                {
                    "name": "frontend",
                    "platform": "vercel",
                    "root_dir": f_root,
                    "runtime": f_runtime,
                    "install_command": f_install,
                    "build_command": f_build,
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
    ui.console.print("    1. [bold]forge set-cred railway[/bold]   — add your Railway API key")
    ui.console.print("    2. [bold]forge set-cred vercel[/bold]   — add your Vercel token")
    ui.console.print("    3. [bold]forge link[/bold]              — link this repo to the project")