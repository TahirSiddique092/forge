import typer
import subprocess
import requests
import time
import tempfile
import shutil
import os
from forge.config import load_config
from forge import ui

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")

worker_app = typer.Typer(help="Manage the local CI worker process.")


@worker_app.command("start")
def worker():
    """
    Start the local CI worker and poll for incoming jobs.

    The worker clones your repository, checks out the pushed commit,
    runs each component's install and test commands inside Docker,
    and reports results back to Forge.

    Keep this process running whenever you expect to push code.
    Docker Desktop must be running before starting the worker.
    """

    try:
        cfg = load_config()
    except Exception:
        ui.error("Not initialized. Run [bold]forge init[/bold] first.")
        raise typer.Exit(1)

    project_id   = cfg.get("project_id")
    worker_token = cfg.get("worker_token")

    if not project_id or not worker_token:
        ui.error("Not linked to a project. Run [bold]forge link[/bold] first.")
        raise typer.Exit(1)

    # Verify Docker is available
    docker_check = subprocess.run(
        ["docker", "info"],
        capture_output=True,
    )
    if docker_check.returncode != 0:
        ui.error("Docker is not running. Start Docker Desktop and try again.")
        raise typer.Exit(1)

    ui.blank()
    ui.success("Worker started.")
    ui.label("Project",  project_id)
    ui.blank()
    ui.console.rule("[dim]Waiting for jobs[/dim]", style="dim")

    while True:
        try:
            r = requests.get(
                f"{BACKEND_URL}/worker/next-job",
                headers={"x-worker-token": worker_token},
                timeout=10,
            )
            job = r.json().get("job")

            if job:
                _run_job(job, worker_token)
            else:
                time.sleep(3)

        except KeyboardInterrupt:
            ui.blank()
            ui.info("Worker stopped.")
            break
        except Exception as e:
            ui.warn(f"Worker error: {e}")
            time.sleep(5)


# ── Job runner ────────────────────────────────────────────────────────────────

def _run_job(job: dict, worker_token: str) -> None:
    run_id = job["run_id"]
    commit = job["commit"]
    repo   = job["repo"]

    ui.blank()
    ui.console.rule(f"[dim]Run #{run_id}  —  {repo}  @  {commit[:7]}[/dim]", style="dim")

    workdir = tempfile.mkdtemp(prefix="forge-")

    try:
        # ── Clone ────────────────────────────────────────────────────────────
        ui.info(f"Cloning  [cyan]{repo}[/cyan]")
        step = _start_step(run_id, "clone", worker_token)

        git_url = f"https://github.com/{repo}.git"
        token_res = requests.get(
            f"{BACKEND_URL}/worker/runs/{run_id}/token",
            headers={"x-worker-token": worker_token},
            timeout=10,
        )
        if token_res.status_code == 200:
            install_tok = token_res.json().get("token")
            if install_tok:
                git_url = f"https://x-access-token:{install_tok}@github.com/{repo}.git"

        r = subprocess.run(
            ["git", "clone", git_url, workdir],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        _finish_step(step, run_id, "success" if r.returncode == 0 else "failed", worker_token, r.stdout, r.stderr)

        if r.returncode != 0:
            ui.error("Clone failed.")
            _report_status(run_id, job, False, worker_token)
            return

        # ── Checkout ─────────────────────────────────────────────────────────
        ui.info(f"Checking out  [cyan]{commit[:7]}[/cyan]")
        step = _start_step(run_id, "checkout", worker_token)

        r = subprocess.run(
            ["git", "checkout", commit],
            cwd=workdir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        _finish_step(step, run_id, "success" if r.returncode == 0 else "failed", worker_token, r.stdout, r.stderr)

        if r.returncode != 0:
            ui.error("Checkout failed.")
            _report_status(run_id, job, False, worker_token)
            return

        # ── Component CI ──────────────────────────────────────────────────────
        components  = job.get("spec", {}).get("components", [])
        all_success = True

        for component in components:
            name     = component["name"]
            root_dir = component["root_dir"]
            image    = _docker_image(component)
            cmd      = _ci_command(component)

            ui.info(f"[{name}]  {image}  →  {cmd[:60]}")
            step = _start_step(run_id, f"ci:{name}", worker_token)

            r = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{workdir}:/app",
                    "-w", "/app",
                    image,
                    "sh", "-c", f"cd {root_dir} && {cmd}",
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=300,
            )

            step_status = "success" if r.returncode == 0 else "failed"
            _finish_step(step, run_id, step_status, worker_token, r.stdout, r.stderr)

            if r.returncode == 0:
                ui.success(f"[{name}]  passed")
            else:
                ui.error(f"[{name}]  failed")
                all_success = False
                break

        # ── Final report ──────────────────────────────────────────────────────
        if all_success:
            ui.success(f"Run #{run_id} passed — all components succeeded.")
        else:
            ui.error(f"Run #{run_id} failed — check [bold]forge logs[/bold] for details.")

        _report_status(run_id, job, all_success, worker_token)

    except subprocess.TimeoutExpired:
        ui.error("Step timed out after 300 seconds.")
        _report_status(run_id, job, False, worker_token)

    except Exception as e:
        ui.error(f"Job execution error: {e}")
        _report_status(run_id, job, False, worker_token)

    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        ui.blank()


# ── Worker API helpers ────────────────────────────────────────────────────────

def _start_step(run_id: int, name: str, token: str) -> int:
    r = requests.post(
        f"{BACKEND_URL}/worker/runs/{run_id}/steps",
        json={"name": name},
        headers={"x-worker-token": token},
        timeout=10,
    )
    return r.json().get("step_id")


def _finish_step(
    step_id: int, run_id: int, status: str, token: str,
    stdout: str = "", stderr: str = ""
) -> None:
    requests.patch(
        f"{BACKEND_URL}/worker/runs/{run_id}/steps/{step_id}",
        json={"status": status, "stdout": stdout, "stderr": stderr},
        headers={"x-worker-token": token},
        timeout=10,
    )


def _report_status(run_id: int, job: dict, success: bool, token: str) -> None:
    requests.patch(
        f"{BACKEND_URL}/worker/runs/{run_id}/status",
        json={
            "success":         success,
            "repo":            job["repo"],
            "check_run_id":    job["check_run_id"],
            "installation_id": job["installation_id"],
        },
        headers={"x-worker-token": token},
        timeout=10,
    )


def _docker_image(component: dict) -> str:
    runtime = component["runtime"]
    version = component.get(
        "runtime_version",
        "20" if runtime in ("node", "nodejs") else "3.10",
    )
    if runtime in ("node", "nodejs"):
        return f"node:{version}"
    if runtime == "python":
        return f"python:{version}"
    raise Exception(f"Unsupported runtime: {runtime}")


def _ci_command(component: dict) -> str:
    install  = component.get("install_command", "")
    test     = component.get("test_command")
    build    = component.get("build_command")
    platform = component.get("platform")

    cmds = []
    if install:
        cmds.append(install)
        
    # Frontend applications (Vercel) compile statics and exit, proving the code builds.
    # Backend scripts (Render) are infinite servers (e.g., uvicorn), so we skip them here.
    if platform == "vercel" and build:
        cmds.append(build)
        
    if test:
        cmds.append(test)
        
    return " && ".join(cmds) if cmds else "echo 'No commands defined'"