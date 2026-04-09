from app.core.database import SessionLocal
from app.models.project import Project
from app.models.run import Run
from app.models.credential import UserCredential
from app.models.repo_binding import RepoBinding
from app.utils.security import decrypt_token
from app.integrations.render import trigger_render_deploy, get_render_service_url, ensure_render_service
from app.integrations.vercel import trigger_vercel_deploy, ensure_vercel_project

def start_deployment_sequence(project_db_id: int, run_id: int, dynamic_envs: dict = {}):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_db_id).first()
        run = db.query(Run).filter(Run.id == run_id).first()
        if not project or not run:
            return

        creds = db.query(UserCredential).filter(UserCredential.user_id == project.owner_id).all()
        cred_map = {c.provider: decrypt_token(c.encrypted_token) for c in creds}

        # Resolve the linked repo for this project
        binding = db.query(RepoBinding).filter(RepoBinding.project_id == project.project_id).first()
        if not binding:
            raise Exception("No repo linked to this project. Run `forge link` first.")
        repo_full_name = binding.repo_full_name  # e.g. "TahirSiddique092/calculator-app"

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

            current_envs = component.get("env_vars", {}).copy()
            current_envs.update(dynamic_envs)

            service_id = ensure_render_service(
                project_name=project.name,
                component_name=component["name"],
                repo_url=repo_full_name,
                runtime=component.get("runtime", "python"),
                root_dir=component.get("root_dir"),
                install_command=component.get("install_command"),
                start_command=component.get("build_command"),
                env_vars=current_envs,
                api_key=cred_map["render"]
            )
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
            current_envs.update(dynamic_envs)
            if backend_url:
                current_envs["NEXT_PUBLIC_API_URL"] = backend_url

            # Create project in Vercel if it doesn't exist yet (safe to call on every deploy)
            ensure_vercel_project(project.name, repo_full_name, cred_map["vercel"])

            deploy_data = trigger_vercel_deploy(
                project_name=project.name,
                repo_url=repo_full_name,
                env_vars=current_envs,
                token=cred_map["vercel"],
                root_dir=component.get("root_dir"),
                build_command=component.get("build_command"),
                install_command=component.get("install_command")
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