import typer
from forge.commands.init         import init
from forge.commands.login        import login
from forge.commands.create       import create
from forge.commands.link         import link
from forge.commands.unlink       import unlink
from forge.commands.status       import status
from forge.commands.logs         import logs
from forge.commands.deploy       import deploy
from forge.commands.deploy_status import deploy_status
from forge.commands.credentials  import set_credential
from forge.commands.worker       import worker_app

app = typer.Typer(
    name="forge",
    help="""
Forge — spec-driven CI/CD for full-stack projects.

\b
Typical workflow:
  forge init                          Detect the git repo
  forge login                         Authenticate via GitHub
  forge create <name>                 Create a new project
  forge set-cred render               Save Render API key
  forge set-cred vercel               Save Vercel token
  forge link <project-id>             Link repo to project
  forge worker start                  Start the local CI worker
  [git push]                          Triggers CI automatically
  forge status                        Check latest run
  forge logs                          View step-by-step logs
  forge deploy                        Deploy after CI passes
  forge deploy-status                 Track deployment progress
""",
    no_args_is_help=True,
    pretty_exceptions_enable=False,   # Keep stack traces clean in prod
)

app.command()(init)
app.command()(login)
app.command()(create)
app.command()(link)
app.command()(unlink)
app.command()(status)
app.command()(logs)
app.command()(deploy)
app.command(name="deploy-status")(deploy_status)
app.command(name="set-cred")(set_credential)

app.add_typer(worker_app, name="worker")

if __name__ == "__main__":
    app()