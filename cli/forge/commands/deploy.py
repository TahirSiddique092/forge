import typer
import requests
import os
import time
import webbrowser
from forge.config import load_config
from forge import ui
from rich.live import Live

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

def deploy():
    """
    Trigger a deployment and follow its progress in real-time.
    """
    try:
        cfg = load_config()
    except Exception:
        ui.error("Not initialized. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    project_id = cfg.get("project_id")
    token      = cfg.get("session_token")

    if not project_id or not token:
        ui.error("Not linked or authenticated. Run [bold]forge link[/bold] and [bold]forge login[/bold].")
        raise typer.Exit(1)

    # 1. Trigger Deployment
    ui.info(f"Initiating deployment for project [cyan]{project_id}[/cyan]...")
    try:
        r = requests.post(
            f"{BACKEND_URL}/projects/{project_id}/deploy",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except requests.RequestException as e:
        ui.error(f"Failed to reach backend: {e}")
        raise typer.Exit(1)

    if r.status_code != 200:
        ui.error(f"Deployment trigger failed ({r.status_code}): {r.text}")
        raise typer.Exit(1)

    ui.success("Deployment sequence started! Tracking progress...")
    ui.blank()

    # 2. Polling Loop with Live UI
    last_status = None
    with Live(ui.console.print("[dim]Waiting for status...[/dim]"), refresh_per_second=1) as live:
        while True:
            try:
                status_res = requests.get(
                    f"{BACKEND_URL}/projects/{project_id}/deploy/status",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if status_res.status_code != 200:
                    continue

                data = status_res.json()
                raw_status = data.get("deploy_status") or "unknown"
                components = data.get("components") or {}

                # Update the Live display
                # We reuse your component table logic for the UI
                live.update(ui.render_deployment_progress(raw_status, components))

                if "success" in raw_status.lower() or "failed" in raw_status.lower():
                    last_status = data
                    break

            except Exception:
                pass # Continue polling on transient network errors

            time.sleep(3) # Poll every 3 seconds

    # 3. Final Result Handling
    raw_final_status = last_status.get("deploy_status", "unknown")
    components = last_status.get("components", {})

    if raw_final_status == "success":
        ui.blank()
        ui.success("Deployment complete.")
        
        # Automatically open the primary frontend URL
        for name, info in components.items():
            url = info.get("url")
            if url and ("vercel.app" in url or "vercel.com" in url):
                ui.info(f"Opening [cyan]{url}[/cyan] in browser...")
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                break
    else:
        ui.blank()
        ui.error(f"Deployment failed: {raw_final_status}")
        ui.info("Check logs or dashboard for details.")