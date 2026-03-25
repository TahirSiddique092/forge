import time
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.project import Project
from app.models.run import Run
from app.integrations.render import trigger_render_deploy, get_render_service_url
from app.integrations.vercel import trigger_vercel_deploy

def start_deployment_sequence(project_db_id: int, run_id: int):
    """
    Orchestrates the full-stack deployment asynchronously.
    Updates the database at each step for real-time CLI status polling.
    """
    # Create a fresh database session for this background task
    db: Session = SessionLocal()
    
    try:
        project = db.query(Project).filter(Project.id == project_db_id).first()
        run = db.query(Run).filter(Run.id == run_id).first()
        
        if not project or not run:
            return

        results = {}
        backend_url = None

        for component in project.spec.get("components", []):
            comp_name = component.get("name", "Unknown")
            
            if component["platform"] == "render":
                run.deploy_status = f"deploying_backend ({comp_name})"
                db.commit()
                
                service_id = component["env_vars"].get("RENDER_SERVICE_ID")
    
                trigger_render_deploy(service_id)
                
                backend_url = get_render_service_url(service_id)
                results["backend"] = {"url": backend_url, "status": "deployed"}

            elif component["platform"] == "vercel":
        
                run.deploy_status = f"deploying_frontend ({comp_name})"
                db.commit()
                
       
                current_envs = component.get("env_vars", {})
                if backend_url:
                    current_envs["NEXT_PUBLIC_API_URL"] = backend_url
                
                deploy_data = trigger_vercel_deploy(
                    project_name=project.name,
                    repo_url=project.deployment_metadata.get("repo_url"), 
                    env_vars=current_envs
                )
                
                results["frontend"] = {
                    "url": deploy_data.get("url"), 
                    "status": "deployed"
                }

        run.deploy_status = "success"
        run.component_results = results
        db.commit()

    except Exception as e:
        if run:
            run.deploy_status = f"failed: {str(e)}"
            db.commit()
    finally:
        db.close()