import typer
import requests
import os
from forge.config import load_config, save_config

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def create(name: str):
    """
    Create a new project dynamically from the CLI without using the portal.
    """
    cfg = load_config()
    session_token = cfg.get("session_token")
    if not session_token:
        typer.echo("❌ Not logged in. Run `forge login` first.")
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
                    "build_command": "pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 10000",
                    "install_command": "pip install -r requirements.txt"
                },
                {
                    "name": "frontend",
                    "platform": "vercel",
                    "root_dir": "frontend",
                    "runtime": "node",
                    "build_command": "npm run build",
                    "install_command": "npm install"
                }
            ]
        }
    }
    
    r = requests.post(
        f"{BACKEND_URL}/projects", 
        json=payload, 
        headers={"Authorization": f"Bearer {session_token}"}
    )
    
    if r.status_code == 200:
        data = r.json()
        proj_id = data["project_details"]["project_id"]
        worker_tok = data["worker_details"]["worker_token"]
        
        cfg["project_id"] = proj_id
        cfg["worker_token"] = worker_tok
        save_config(cfg)
        
        typer.echo(f"🎉 Successfully created project '{name}'!")
        typer.echo(f"🔗 Linked this directory to {proj_id}.")
        typer.echo("⚡ Next: Configure your specific platform credentials using `forge set-cred` if unconfigured, then link to your Github using `forge link`.")
    else:
        typer.echo(f"❌ Failed to create project: {r.text}")
