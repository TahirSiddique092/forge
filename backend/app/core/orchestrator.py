from app.core.database import SessionLocal
from app.models.project import Project
from app.models.run import Run
from app.models.credential import UserCredential
from app.models.repo_binding import RepoBinding
from app.utils.security import decrypt_token
from app.integrations.railway import deploy_to_railway
from app.integrations.vercel import trigger_vercel_deploy, ensure_vercel_project
from sqlalchemy.orm.attributes import flag_modified
import logging

logger = logging.getLogger(__name__)


def start_deployment_sequence(
    project_db_id: int,
    run_id:        int,
    component_envs: dict = {},
):
    db = SessionLocal()
    run = None

    try:
        project = db.query(Project).filter(Project.id == project_db_id).first()
        run     = db.query(Run).filter(Run.id == run_id).first()

        if not project or not run:
            logger.error(f"Deploy aborted: project or run not found (project_db_id={project_db_id}, run_id={run_id})")
            return

        # Decrypt all credentials for this user
        creds    = db.query(UserCredential).filter(UserCredential.user_id == project.owner_id).all()
        cred_map = {c.provider: decrypt_token(c.encrypted_token) for c in creds}

        # Resolve repo binding
        binding = db.query(RepoBinding).filter(RepoBinding.project_id == project.project_id).first()
        if not binding:
            raise Exception("No repo linked to this project. Run `forge link` first.")

        repo_full_name = binding.repo_full_name   # e.g. "owner/repo"
        branch         = "main"

        results      = {}
        backend_urls = {}

        components         = project.spec.get("components", [])
        railway_components = [c for c in components if c["platform"] == "railway"]
        vercel_components  = [c for c in components if c["platform"] == "vercel"]

        # ── Pass 1: deploy all backends to Railway ────────────────────────────
        for component in railway_components:
            if "railway" not in cred_map:
                raise Exception(
                    "Missing Railway credentials. Run `forge set-cred railway`."
                )

            name = component["name"]
            run.deploy_status = f"deploying_backend ({name})"
            db.commit()

            # Merge spec-level env vars with .env.forge overrides
            current_envs = component.get("env_vars", {}).copy()
            comp_dir     = component.get("root_dir", "").strip("/")
            overrides    = (
                component_envs.get(comp_dir)
                or component_envs.get(name)
                or {}
            )
            current_envs.update(overrides)

            url = deploy_to_railway(
                project_name   = project.name,
                component_name = name,
                repo_full_name = repo_full_name,
                root_dir       = component.get("root_dir", ""),
                branch         = branch,
                start_command  = component.get("build_command"),
                build_command  = component.get("install_command"),
                env_vars       = current_envs,
                api_key        = cred_map["railway"],
            )

            backend_urls[name] = url
            results[name]      = {"url": url, "status": "deployed", "platform": "railway"}

            run.component_results = dict(results)
            flag_modified(run, "component_results")
            db.commit()

            logger.info(f"[{name}] Railway deploy triggered — {url}")

        # Use the first Railway URL as the BACKEND_URL injected into frontends
        backend_url = next(iter(backend_urls.values()), None)

        # ── Pass 2: deploy all frontends to Vercel ────────────────────────────
        for component in vercel_components:
            if "vercel" not in cred_map:
                raise Exception(
                    "Missing Vercel credentials. Run `forge set-cred vercel`."
                )

            name = component["name"]
            run.deploy_status = f"deploying_frontend ({name})"
            db.commit()

            current_envs = component.get("env_vars", {}).copy()
            comp_dir     = component.get("root_dir", "").strip("/")
            overrides    = (
                component_envs.get(comp_dir)
                or component_envs.get(name)
                or {}
            )
            current_envs.update(overrides)

            # Always inject the backend URL so frontends can reach the API
            if backend_url:
                current_envs["BACKEND_URL"] = backend_url

            ensure_vercel_project(project.name, repo_full_name, cred_map["vercel"])

            deploy_data = trigger_vercel_deploy(
                project_name    = project.name,
                repo_url        = repo_full_name,
                env_vars        = current_envs,
                token           = cred_map["vercel"],
                root_dir        = component.get("root_dir"),
                build_command   = component.get("build_command"),
                install_command = component.get("install_command"),
            )

            results[name] = {
                "url":      deploy_data.get("url"),
                "status":   "deployed",
                "platform": "vercel",
            }

            run.component_results = dict(results)
            flag_modified(run, "component_results")
            db.commit()

            logger.info(f"[{name}] Vercel deploy triggered — {deploy_data.get('url')}")

        run.deploy_status    = "success"
        run.component_results = dict(results)
        db.commit()

        logger.info(f"Deployment complete for project {project.project_id}")

    except Exception as e:
        logger.error(f"Deployment failed: {e}", exc_info=True)
        if run:
            run.deploy_status = f"failed: {str(e)}"
            db.commit()

    finally:
        db.close()