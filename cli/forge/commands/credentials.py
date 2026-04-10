import typer
import requests
import os
from forge.config import load_config
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

_VALID_PROVIDERS = ["render", "vercel"]


def set_credential(
    provider: str = typer.Argument(
        ...,
        help="Hosting provider: render or vercel",
    ),
    token: str = typer.Option(
        ...,
        prompt="API token",
        hide_input=True,
        help="API key / token for the provider (input is hidden)",
    ),
):
    """
    Save a hosting provider API token.

    The token is encrypted at rest and never stored locally.
    Run this once per provider before your first deployment.

    \b
    Providers:
      render   — Render.com API key
      vercel   — Vercel personal access token
    """

    if provider not in _VALID_PROVIDERS:
        ui.error(
            f"Unknown provider '{provider}'. "
            f"Valid options: {', '.join(_VALID_PROVIDERS)}"
        )
        raise typer.Exit(1)

    try:
        cfg = load_config()
    except Exception:
        ui.error("Not initialized. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    session_token = cfg.get("session_token")
    if not session_token:
        ui.error("Not authenticated. Run [bold]forge login[/bold] first.")
        raise typer.Exit(1)

    with ui.console.status(f"[dim]Saving {provider} credentials...[/dim]", spinner="dots"):
        r = requests.post(
            f"{BACKEND_URL}/credentials",
            json={"provider": provider, "token": token},
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=10,
        )

    if r.status_code == 200:
        ui.success(f"{provider.capitalize()} credentials saved.")
    else:
        ui.error(f"Failed to save credentials: {r.text}")
        raise typer.Exit(1)