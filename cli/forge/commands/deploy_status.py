import typer
import requests
import os
import webbrowser
from forge.config import load_config
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-cpj5.onrender.com")


def deploy_status():
    """
    Show the current status of the most recent deployment.
    A full deployment across multiple components can take
    several minutes depending on your Railway and Vercel configurations.
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

    try:
        r = requests.get(
            f"{BACKEND_URL}/projects/{project_id}/deploy/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.RequestException as e:
        ui.error(f"Request failed: {e}")
        raise typer.Exit(1)

    if r.status_code != 200:
        ui.error(f"Could not fetch deployment status ({r.status_code}).")
        raise typer.Exit(1)

    data       = r.json()
    raw_status = data.get("deploy_status") or "unknown"
    components = data.get("components") or {}

    # ── Header ────────────────────────────────────────────────────────────────
    ui.blank()
    ui.label("Project",    project_id)
    ui.console.print(f"  [dim]{'Status':<14}[/dim]", end="")
    ui.console.print(ui.status_badge(raw_status))
    ui.blank()

    if raw_status == "no_deployment_found":
        ui.warn("No deployment has been triggered yet. Run [bold]forge deploy[/bold] first.")
        return

    # ── Component breakdown ───────────────────────────────────────────────────
    if components:
        ui.console.rule("[dim]Components[/dim]", style="dim")
        ui.blank()
        ui.deploy_components_table(components)

    # ── Final outcome ─────────────────────────────────────────────────────────
    if raw_status == "success":
        ui.blank()
        ui.success("Deployment complete.")

        # Open the first Vercel URL in the browser
        for name, info in components.items():
            url = info.get("url") or ""
            if "vercel.app" in url or "vercel.com" in url:
                ui.info(f"Opening [cyan]{url}[/cyan] in your browser.")
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                break

    elif "failed" in raw_status.lower():
        ui.blank()
        reason = raw_status.replace("failed: ", "").strip()
        
        if "GITHUB_INTEGRATION_MISSING" in reason:
            parts = reason.split("|")
            provider_part = parts[0].split(":")[1].strip().lower()
            repo = parts[1].strip() if len(parts) > 1 else "your repository"
            
            app_name = "Railway" if provider_part == "railway" else "Vercel"
            provider_part = "railway-app" if provider_part == "railway" else "vercel"
            app_url = f"https://github.com/apps/{provider_part}"

            ui.error(f"Deployment failed: {app_name} cannot access your repository.")
            ui.blank()
            ui.rule("Action Required")
            ui.blank()
            ui.info(f"The {app_name} GitHub App is not installed or lacks permissions.")
            ui.blank()
            
            ui.label("1. Install", app_url)
            ui.label("2. Permission", f"Grant access to: {repo}")
            ui.label("3. Retry", "Run [bold]forge deploy[/bold] again")
            
            ui.blank()
            ui.rule()
        else:
            ui.error(f"Deployment failed: {reason}")
            ui.info("Check your Railway / Vercel dashboard for detailed logs.")

    else:
        ui.blank()
        ui.info("Deployment is in progress. Run this command again to check for updates.")