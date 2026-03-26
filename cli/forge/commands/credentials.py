import typer
import requests
import os
from forge.config import load_config

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def set_credential(
    provider: str = typer.Argument(..., help="Provider name: 'render' or 'vercel'"),
    token: str = typer.Option(..., prompt=True, hide_input=True, help="API Token/Key")
):
    """
    Securely set your hosting provider credentials.
    """
    cfg = load_config()
    session_token = cfg.get("session_token")
    
    if not session_token:
        typer.echo("❌ Not logged in.")
        raise typer.Exit(1)

    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {"provider": provider, "token": token}
    
    r = requests.post(f"{BACKEND_URL}/credentials", json=payload, headers=headers)
    
    if r.status_code == 200:
        typer.echo(f"✅ {provider.capitalize()} credentials saved securely!")
    else:
        typer.echo(f"❌ Failed: {r.text}")