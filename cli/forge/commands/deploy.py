import typer
import requests
import os
from forge.config import load_config

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def deploy():
    """
    Trigger the full-stack deployment (Backend to Render, Frontend to Vercel).
    Only works if the latest CI build was successful.
    """
    cfg = load_config()
    project_id = cfg.get("project_id")
    # We need the user's session token for authentication
    # In a real app, you'd store this during a 'forge login' command.
    token = cfg.get("session_token") 

    if not project_id:
        typer.echo("❌ Not linked to a project. Run `forge link` first.")
        raise typer.Exit(1)

    typer.echo(f"🚀 Initiating deployment for project {project_id}...")

    headers = {"Authorization": f"Bearer {token}"}
    
    component_envs = {}
    for root, dirs, files in os.walk("."):
        if ".env.forge" in files:
            if any(part.startswith('.') and part != '.' for part in root.split(os.sep)):
                continue
            
            comp_name = os.path.normpath(root)
            if comp_name == ".":
                comp_name = ""
                
            envs = {}
            with open(os.path.join(root, ".env.forge"), "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        envs[k.strip()] = v.strip().strip("'").strip('"')
            
            if envs:
                typer.echo(f"📦 Found .env.forge for component '{comp_name}'")
                component_envs[comp_name] = envs

    r = requests.post(f"{BACKEND_URL}/projects/{project_id}/deploy", headers=headers, json={"component_envs": component_envs})

    if r.status_code == 400:
        typer.echo(f"🛑 Error: {r.json().get('detail')}")
        typer.echo("Please ensure your latest code push passed all tests.")
        raise typer.Exit(1)
    
    if r.status_code != 200:
        typer.echo(f"❌ Deployment failed to start: {r.text}")
        raise typer.Exit(1)

    data = r.json()
    typer.echo("✅ Deployment initiated successfully!")
    typer.echo("Run `forge deploy-status` to track progress.")