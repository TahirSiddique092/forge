import typer
import webbrowser
import os
import requests
import secrets
import time
from forge.config import load_config, save_config

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def login():
    """
    Authenticate with Forge via GitHub.
    """
    auth_code = secrets.token_hex(16)
    login_url = f"{BACKEND_URL}/auth/github?auth_code={auth_code}"
    
    typer.echo("Opening your browser to authenticate with GitHub...")
    webbrowser.open(login_url)
    typer.echo("Waiting for authentication to complete...")
    
    token = None
    # Poll for up to 5 minutes
    for _ in range(150):
        try:
            r = requests.get(f"{BACKEND_URL}/auth/poll?auth_code={auth_code}")
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    token = data.get("session_token")
                    break
        except Exception:
            pass
        time.sleep(2)
        
    if not token:
        typer.echo("❌ Authentication timed out.")
        raise typer.Exit(1)
        
    try:
        cfg = load_config()
    except:
        cfg = {}

    cfg["session_token"] = token
    save_config(cfg)
    
    typer.echo("✅ Successfully authenticated!")