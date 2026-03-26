import typer
import webbrowser
import os
from forge.config import load_config, save_config

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def login():
    """
    Authenticate with Forge via GitHub.
    """
    login_url = f"{BACKEND_URL}/auth/github"
    typer.echo("Opening your browser to authenticate with GitHub...")
    webbrowser.open(login_url)
    
    typer.echo("\nAfter logging in, you will see a 'session_token' in the JSON response.")
    token = typer.prompt("Please paste your session token here")
    
    try:
        cfg = load_config()
    except:
        cfg = {}

    cfg["session_token"] = token
    save_config(cfg)
    
    typer.echo("✅ Successfully authenticated!")