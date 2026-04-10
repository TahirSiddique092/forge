import typer
import os
import subprocess
from forge.config import load_config, save_config
from forge import ui


def init():
    """Initialize forge in the current git repository."""

    if not os.path.exists(".git"):
        ui.error("Not a git repository. Run this command from your project root.")
        raise typer.Exit(1)

    try:
        repo = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        repo = "unknown"

    try:
        config = load_config()
    except Exception:
        config = {}

    config["repo"] = repo
    save_config(config)

    ui.success("forge initialized")
    ui.blank()
    ui.label("Repository", repo)
    ui.blank()
    ui.info("Next: run [bold]forge login[/bold] to authenticate with GitHub.")