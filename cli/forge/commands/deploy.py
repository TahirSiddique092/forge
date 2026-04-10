import typer
import requests
import os
from forge.config import load_config, get_auth_headers
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")


def deploy():
    """
    Trigger a full-stack deployment for the current project.

    Requires the most recent CI run to have passed. Env vars are read
    from .env.forge files found in component subdirectories.

    \b
    .env.forge format (one per component directory):
      KEY=value
      ANOTHER_KEY=another_value

    These files should be gitignored and never committed.
    """

    try:
        cfg = load_config()
    except Exception:
        ui.error("Not initialized. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    project_id = cfg.get("project_id")
    if not project_id:
        ui.error("Not linked to a project. Run [bold]forge link[/bold] first.")
        raise typer.Exit(1)

    token = cfg.get("session_token")
    if not token:
        ui.error("Not authenticated. Run [bold]forge login[/bold] first.")
        raise typer.Exit(1)

    # ── Collect .env.forge files ──────────────────────────────────────────────
    component_envs = {}
    for root, dirs, files in os.walk("."):
        # Skip hidden directories (except root ".")
        if any(
            part.startswith(".") and part != "."
            for part in root.split(os.sep)
        ):
            continue

        if ".env.forge" not in files:
            continue

        comp_path = os.path.normpath(root)
        if comp_path == ".":
            comp_path = ""

        envs = {}
        env_file = os.path.join(root, ".env.forge")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    envs[k.strip()] = v.strip().strip("'").strip('"')

        if envs:
            ui.info(f"Found .env.forge  [dim]{comp_path or '(root)'}[/dim]  ({len(envs)} vars)")
            component_envs[comp_path] = envs

    # ── Send deploy request ───────────────────────────────────────────────────
    ui.blank()
    with ui.console.status("[dim]Initiating deployment...[/dim]", spinner="dots"):
        r = requests.post(
            f"{BACKEND_URL}/projects/{project_id}/deploy",
            headers={"Authorization": f"Bearer {token}"},
            json={"component_envs": component_envs},
            timeout=15,
        )

    if r.status_code == 400:
        ui.error(r.json().get("detail", "Deployment rejected by server."))
        ui.info("Ensure your latest push passed CI before deploying.")
        raise typer.Exit(1)

    if r.status_code != 200:
        ui.error(f"Deployment request failed ({r.status_code}): {r.text}")
        raise typer.Exit(1)

    ui.success("Deployment initiated.")
    ui.blank()
    ui.info("Run [bold]forge deploy-status[/bold] to track progress.")