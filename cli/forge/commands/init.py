import typer
import os
import subprocess
from forge.config import save_config

def init():

    if not os.path.exists(".git"):
        typer.echo("Not a git repository")
        raise typer.Exit(1)

    repo = subprocess.check_output(
        ["git", "remote", "get-url", "origin"]
    ).decode().strip()

    config = {
        "repo": repo
    }

    save_config(config)

    typer.echo("forge initialized")
    typer.echo(f"Repo: {repo}")
