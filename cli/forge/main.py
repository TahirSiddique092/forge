import typer
from forge.commands.init import init
from forge.commands.link import link
from forge.commands.status import status
from forge.commands.logs import logs
from forge.commands.unlink import unlink
from forge.commands.worker import worker_app
from forge.commands.login import login
from forge.commands.deploy import deploy             
from forge.commands.deploy_status import deploy_status 
from forge.commands.credentials import set_credential
from forge.commands.create import create

app = typer.Typer(help="forge — spec-driven CI/CD for Hackathons")

app.command()(init)
app.command()(link)
app.command()(status)
app.command()(logs)
app.command()(unlink)
app.command()(login)
app.command(name="set-cred")(set_credential)
app.command()(deploy)               
app.command(name="deploy-status")(deploy_status) 
app.command()(create) 

app.add_typer(worker_app, name="worker")

if __name__ == "__main__":
    app()
