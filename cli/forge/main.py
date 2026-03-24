import typer
from forge.commands.init import init
from forge.commands.link import link
from forge.commands.status import status
from forge.commands.logs import logs
from forge.commands.unlink import unlink
from forge.commands.worker import worker_app

app = typer.Typer(help="forge — spec-driven CI")

app.command()(init)
app.command()(link)
app.command()(status)
app.command()(logs)
app.command()(unlink)

app.add_typer(worker_app, name="worker")

if __name__ == "__main__":
    app()
