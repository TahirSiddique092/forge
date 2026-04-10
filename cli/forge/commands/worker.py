import typer
import subprocess
import requests
import time
import tempfile
import shutil
from forge.config import load_config
import os

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "https://forge-backend-wwp9.onrender.com")
worker_app = typer.Typer()

@worker_app.command("start")
def worker():
    """
    Run worker locally and poll for multi-component CI jobs.
    """
    cfg = load_config()
    project_id = cfg.get("project_id")
    worker_token = cfg.get("worker_token")
    
    if not project_id or not worker_token:
        typer.echo("Not linked to any project. Run `forge link` first.")
        raise typer.Exit(1)
    
    r = subprocess.run(["docker", "info"], capture_output=True)
    if r.returncode != 0:
        typer.echo("Docker is not running. Please start Docker Desktop.")
        raise typer.Exit(1)
    
    typer.echo(f"forge worker running ({project_id})")
    typer.echo(f"Waiting for jobs...")
    
    while True:
        try:
            r = requests.get(f"{BACKEND_URL}/worker/next-job", headers={"x-worker-token": worker_token})
            job = r.json().get("job")
    
            if job:
                typer.echo(f"Running CI for commit {job['commit'][:7]}")
                run_job(job, worker_token) 
            else:
                time.sleep(3)

        except Exception as e:
            typer.echo(f"Error: {e}")
            time.sleep(5)

def run_job(job, worker_token):
    run_id = job["run_id"]
    spec = job["spec"]
    commit = job["commit"]
    repo = job["repo"]
    
    workdir = tempfile.mkdtemp(prefix="forge-")
    
    try:
        typer.echo(f"  Cloning {repo}...")
        step = start_step(run_id, "clone", worker_token)
        
        # Fetch installation token
        token_res = requests.get(f"{BACKEND_URL}/worker/runs/{run_id}/token", headers={"x-worker-token": worker_token})
        git_url = f"https://github.com/{repo}.git"
        if token_res.status_code == 200:
            install_token = token_res.json().get("token")
            if install_token:
                git_url = f"https://x-access-token:{install_token}@github.com/{repo}.git"

        r = subprocess.run(
            ["git", "clone", git_url, workdir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        finish_step(step, run_id, "success" if r.returncode == 0 else "failed", worker_token, r.stdout, r.stderr)
        if r.returncode != 0:
            typer.echo(f"  Clone failed.")
            report_status(run_id, job, False, worker_token)
            return
        typer.echo(f"  Clone complete.")

        typer.echo(f"  Checking out {commit[:7]}...")
        step = start_step(run_id, "checkout", worker_token)
        r = subprocess.run(
            ["git", "checkout", commit],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        finish_step(step, run_id, "success" if r.returncode == 0 else "failed", worker_token, r.stdout, r.stderr)
        if r.returncode != 0:
            typer.echo(f"  Checkout failed.")
            report_status(run_id, job, False, worker_token)
            return
        typer.echo(f"  Checkout complete.")

        spec = job.get("spec", {})
        components = spec.get("components", [])
        all_success = True

        for component in components:
            name = component["name"]
            root_dir = component["root_dir"]
            image = get_docker_image(component)

            step_name = f"ci:{name}"
            step = start_step(run_id, step_name, worker_token)

            cmd = f"cd {root_dir} && {build_command(component)}"

            typer.echo(f"  [{name}] Running install...")
            r = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{workdir}:/app",
                    "-w", "/app",
                    image,
                    "sh", "-c", cmd
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300
            )

            status = "success" if r.returncode == 0 else "failed"
            finish_step(step, run_id, status, worker_token, r.stdout, r.stderr)

            if r.returncode != 0:
                typer.echo(f"  [{name}] Install failed.")
                all_success = False
                break
            typer.echo(f"  [{name}] Install complete.")

        if all_success:
            typer.echo(f"  All components passed.")
        else:
            typer.echo(f"  CI failed. Check the dashboard for logs.")
        report_status(run_id, job, all_success, worker_token)

    except subprocess.TimeoutExpired:
        typer.echo(f"  Step timed out after 300s.")
        report_status(run_id, job, False, worker_token)
    except Exception as e:
        typer.echo(f"  Job execution failed: {e}")
        report_status(run_id, job, False, worker_token)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

def start_step(run_id, name, worker_token):
    r = requests.post(f"{BACKEND_URL}/worker/runs/{run_id}/steps", json={"name": name}, headers={"x-worker-token": worker_token})
    return r.json().get("step_id")

def finish_step(step_id, run_id, status, worker_token, stdout="", stderr=""):
    requests.patch(
        f"{BACKEND_URL}/worker/runs/{run_id}/steps/{step_id}",
        json={"status": status, "stdout": stdout, "stderr": stderr},
        headers={"x-worker-token": worker_token}
    )

def get_docker_image(component: dict):
    runtime = component["runtime"]
    version = component.get("runtime_version", "20" if runtime == "node" else "3.10")

    if runtime == "node":
        return f"node:{version}"
    if runtime == "python":
        return f"python:{version}"

    raise Exception(f"Unsupported runtime: {runtime}")

def build_command(component: dict):
    install = component.get("install_command", "")
    test = component.get("test_command")

    if test:
        return f"{install} && {test}"
    return install

def report_status(run_id, job, success, worker_token):
    requests.patch(
        f"{BACKEND_URL}/worker/runs/{run_id}/status",
        json={
            "success": success,
            "repo": job["repo"],
            "check_run_id": job["check_run_id"],
            "installation_id": job["installation_id"]
        },
        headers={"x-worker-token": worker_token}
    )