import typer
import subprocess
import requests
import time
import tempfile
import shutil
from forge.config import load_config
import os

BACKEND_URL = os.getenv("FORGE_BACKEND_URL", "http://localhost:8000")
worker_app = typer.Typer()

@worker_app.command("start")
def worker():
    """
    Run worker locally
    """
    cfg = load_config()
    project_id = cfg.get("project_id")
    worker_token = cfg.get("worker_token")
    
    if not project_id or not worker_token:
        typer.echo("Not linked to any project. Run `forge link`.")
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
                typer.echo(f"Running build for commit {job['commit'][:7]}")
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
    
    image = get_docker_image(spec)
    workdir = tempfile.mkdtemp(prefix="forge-")
    
    try:
        # STEP: clone
        step = start_step(run_id, "clone", worker_token)
        r = subprocess.run(
            ["git", "clone", f"https://github.com/{repo}.git", workdir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        finish_step(step, run_id, "success" if r.returncode == 0 else "failed", worker_token, r.stdout, r.stderr)
        if r.returncode != 0:
            report_status(run_id, job, False, worker_token)
            return 

        # STEP: checkout
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
            report_status(run_id, job, False, worker_token)
            return 

        # STEP: ci
        step = start_step(run_id, "ci", worker_token)
        r = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{workdir}:/app",
                "-w", "/app",
                image,
                "sh", "-c", build_command(spec)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )
        finish_step(step, run_id, "success" if r.returncode == 0 else "failed", worker_token, r.stdout, r.stderr)
        report_status(run_id, job, r.returncode == 0, worker_token)

    except subprocess.TimeoutExpired:
        report_status(run_id, job, False, worker_token)

    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    

def start_step(run_id, name, worker_token):
    r = requests.post(f"{BACKEND_URL}/worker/runs/{run_id}/steps", json={"name": name}, headers={"x-worker-token": worker_token})
    step_id = r.json().get("step_id")
    return step_id


def finish_step(step_id, run_id, status, worker_token, stdout="", stderr=""):
    requests.patch(
        f"{BACKEND_URL}/worker/runs/{run_id}/steps/{step_id}",
        json={"status": status, "stdout": stdout, "stderr": stderr},
        headers={"x-worker-token": worker_token}
    )

def get_docker_image(spec: dict):
    runtime = spec["runtime"]
    version = spec["runtime_version"]

    if runtime == "node":
        return f"node:{version}"
    if runtime == "python":
        return f"python:{version}"

    raise Exception(f"Unsupported runtime: {runtime}")


def build_command(spec: dict):
    commands = spec["commands"]
    cmd = commands["install"]

    if commands.get("test"):
        cmd += f" && {commands['test']}"
    else:
        cmd += f" && {commands['build']}"

    return cmd

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