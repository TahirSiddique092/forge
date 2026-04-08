from app.core.database import SessionLocal
from app.models.project import Project
from app.models.run import Run
from app.models.credential import UserCredential
from app.utils.security import decrypt_token
from app.integrations.render import trigger_render_deploy, get_render_service_url
from app.integrations.vercel import trigger_vercel_deploy

def start_deployment_sequence(project_db_id: int, run_id: int):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_db_id).first()
        run = db.query(Run).filter(Run.id == run_id).first()
        if not project or not run:
            return

        creds = db.query(UserCredential).filter(UserCredential.user_id == project.owner_id).all()
        cred_map = {c.provider: decrypt_token(c.encrypted_token) for c in creds}

        results = {}
        backend_urls = {}  # component name -> deployed URL

        components = project.spec.get("components", [])
        render_components = [c for c in components if c["platform"] == "render"]
        vercel_components = [c for c in components if c["platform"] == "vercel"]

        # --- Pass 1: deploy all backends first ---
        # This ensures backend URLs are available before any frontend deploys.
        for component in render_components:
            if "render" not in cred_map:
                raise Exception("Missing Render credentials. Run `forge set-cred render`.")

            run.deploy_status = f"deploying_backend ({component['name']})"
            db.commit()

            service_id = component["env_vars"].get("RENDER_SERVICE_ID")
            trigger_render_deploy(service_id, cred_map["render"])
            url = get_render_service_url(service_id, cred_map["render"])
            backend_urls[component["name"]] = url
            results[component["name"]] = {"url": url, "status": "deployed"}

        # Use the first render URL as the general backend URL injected into frontends.
        backend_url = next(iter(backend_urls.values()), None)

        # --- Pass 2: deploy all frontends, injecting the backend URL ---
        for component in vercel_components:
            if "vercel" not in cred_map:
                raise Exception("Missing Vercel credentials. Run `forge set-cred vercel`.")

            run.deploy_status = f"deploying_frontend ({component['name']})"
            db.commit()

            current_envs = component.get("env_vars", {}).copy()
            if backend_url:
                current_envs["NEXT_PUBLIC_API_URL"] = backend_url

            deploy_data = trigger_vercel_deploy(
                project_name=project.name,
                repo_url=project.deployment_metadata.get("repo_url"),
                env_vars=current_envs,
                token=cred_map["vercel"]
            )
            results[component["name"]] = {"url": deploy_data.get("url"), "status": "deployed"}

        run.deploy_status = "success"
        run.component_results = results
        db.commit()

    except Exception as e:
        if run:
            run.deploy_status = f"failed: {str(e)}"
            db.commit()
    finally:
        db.close()