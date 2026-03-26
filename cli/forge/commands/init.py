import typer
import os
import subprocess
from forge.config import load_config, save_config

def init():
    if not os.path.exists(".git"):
        typer.echo("Not a git repository")
        raise typer.Exit(1)

    try:
        repo = subprocess.check_output(
            ["git", "remote", "get-url", "origin"]
        ).decode().strip()
    except:
        repo = "unknown"

    try:
        config = load_config()
    except:
        config = {}

    config["repo"] = repo
    save_config(config)

    typer.echo("forge initialized")
    typer.echo(f"Repo: {repo}")