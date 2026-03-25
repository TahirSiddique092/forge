from app.core.database import SessionLocal
from app.models.project import Project
from app.models.run import Run
from app.models.credential import UserCredential # Added
from app.utils.security import decrypt_token      # Added
from app.integrations.render import trigger_render_deploy, get_render_service_url
from app.integrations.vercel import trigger_vercel_deploy

def start_deployment_sequence(project_db_id: int, run_id: int):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_db_id).first()
        run = db.query(Run).filter(Run.id == run_id).first()
        if not project or not run: return

        creds = db.query(UserCredential).filter(UserCredential.user_id == project.owner_id).all()
        cred_map = {c.provider: decrypt_token(c.encrypted_token) for c in creds}

        results = {}
        backend_url = None

        for component in project.spec.get("components", []):
            platform = component["platform"]
            
            if platform == "render":
                if "render" not in cred_map:
                    raise Exception("Missing Render credentials. Run `forge set-cred render`.")
                
                run.deploy_status = f"deploying_backend ({component['name']})"
                db.commit()
                
                service_id = component["env_vars"].get("RENDER_SERVICE_ID")
                trigger_render_deploy(service_id, cred_map["render"])
                backend_url = get_render_service_url(service_id, cred_map["render"])
                results["backend"] = {"url": backend_url, "status": "deployed"}

            elif platform == "vercel":
                if "vercel" not in cred_map:
                    raise Exception("Missing Vercel credentials. Run `forge set-cred vercel`.")

                run.deploy_status = f"deploying_frontend ({component['name']})"
                db.commit()

                current_envs = component.get("env_vars", {})
                if backend_url:
                    current_envs["NEXT_PUBLIC_API_URL"] = backend_url
                
                deploy_data = trigger_vercel_deploy(
                    project_name=project.name,
                    repo_url=project.deployment_metadata.get("repo_url"), 
                    env_vars=current_envs,
                    token=cred_map["vercel"]
                )
                results["frontend"] = {"url": deploy_data.get("url"), "status": "deployed"}

        run.deploy_status = "success"
        run.component_results = results
        db.commit()

    except Exception as e:
        if run:
            run.deploy_status = f"failed: {str(e)}"
            db.commit()
    finally:
        db.close()