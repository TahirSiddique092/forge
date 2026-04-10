import typer
import webbrowser
import os
import requests
import secrets
import time
from forge.config import load_config, save_config
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")


def login():
    """Authenticate with Forge via GitHub OAuth."""

    auth_code = secrets.token_hex(16)
    login_url = f"{BACKEND_URL}/auth/github?auth_code={auth_code}"

    ui.blank()
    ui.info("Opening GitHub in your browser to complete authentication.")
    ui.info(f"If the browser does not open, visit: [cyan]{login_url}[/cyan]")
    ui.blank()

    webbrowser.open(login_url)

    token = None
    with ui.console.status("[dim]Waiting for authentication...[/dim]", spinner="dots"):
        for _ in range(150):  # 5 minutes
            try:
                r = requests.get(
                    f"{BACKEND_URL}/auth/poll?auth_code={auth_code}",
                    timeout=5,
                )
                if r.status_code == 200 and r.json().get("status") == "success":
                    token = r.json().get("session_token")
                    break
            except Exception:
                pass
            time.sleep(2)

    if not token:
        ui.error("Authentication timed out. Please try again.")
        raise typer.Exit(1)

    try:
        cfg = load_config()
    except Exception:
        cfg = {}

    cfg["session_token"] = token
    save_config(cfg)

    ui.success("Authenticated successfully.")
    ui.blank()
    ui.info("Next: run [bold]forge create <name>[/bold] to create a project.")