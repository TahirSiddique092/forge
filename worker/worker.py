import os
import json
import ssl
import redis
import subprocess
import tempfile
import shutil
from dotenv import load_dotenv
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

from shared.github.auth import get_installation_token
from shared.github.checks import complete_check_run


load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=ssl.CERT_NONE
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

QUEUE_NAME = "ci_jobs"

def run_job(job):
    run_id = job["run_id"]
    project_id = job["project_id"]
    repo = job["repo"]
    commit = job["commit"]
    check_run_id = job["check_run_id"]
    installation_id = job["installation_id"]

    db = SessionLocal()

    try:
        print("Worker started doing job...")
        ci_result = run_ci(job)
        success = ci_result["success"]


        token = get_installation_token(installation_id)
       
        complete_check_run(
            token=token,
            repo=repo,
            check_run_id=check_run_id,
            conclusion="success" if success else "failure"
        )


        status = "success" if success else "failed"

    except Exception as e:
        print("\n🔥 EXCEPTION OCCURRED")
        print("❌ Error:", repr(e))

        try:
            print("🔐 Retrying installation token...")
            token = get_installation_token(installation_id)

            print("📡 Reporting failure to GitHub...")
            complete_check_run(
                token=token,
                repo=repo,
                check_run_id=check_run_id,
                conclusion="failure",
                output={
                    "title": "forge CI failed",
                    "summary": str(e)
                }
            )
        except Exception as inner:
            print("🚨 FAILED TO REPORT TO GITHUB:", repr(inner))

        status = "failed"

    db.execute(
        text("""
            UPDATE runs
            SET status=:status,
                stdout=:stdout,
                stderr=:stderr
            WHERE id=:id
        """),
        {
            "status": status,
            "stdout": ci_result["stdout"],
            "stderr": ci_result["stderr"],
            "id": run_id
        }
    )

    db.commit()
    print("Worker completed the job !")


def run_ci(job):
    repo = job["repo"]
    commit = job["commit"]
    project_id = job["project_id"]

    db = SessionLocal()
    spec = get_project_spec(project_id, db)

    image = get_docker_image(spec)
    command = build_command(spec)

    workdir = tempfile.mkdtemp(prefix="forge-")

    try:
        subprocess.run(
            ["git", "clone", f"https://github.com/{repo}.git", workdir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            ["git", "checkout", commit],
            cwd=workdir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{workdir}:/app",
                "-w", "/app",
                image,
                "sh", "-c", command
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }


    except subprocess.TimeoutExpired:
        print("⏱️ CI TIMED OUT")
        return False

    except subprocess.CalledProcessError as e:
        print("❌ CI FAILED")
        print(e.stdout)
        print(e.stderr)
        return False

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def get_project_spec(project_id: str, db):
    result = db.execute(
        text("SELECT spec FROM projects WHERE project_id = :pid"),
        {"pid": project_id}
    ).fetchone()

    if not result:
        raise Exception(f"Project {project_id} not found")

    return result[0]


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



def main():
    print("🧑‍🏭 CI Worker started, waiting for jobs...")
    while True:
        _, job_data = redis_client.blpop(QUEUE_NAME)
        job = json.loads(job_data)
        run_job(job)


if __name__ == "__main__":
    main()
