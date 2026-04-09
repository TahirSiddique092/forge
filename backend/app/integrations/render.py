import requests
import re

def sanitize_render_name(name: str) -> str:
    name = name.lower()
    name = name.replace(" ", "-").replace("_", "-")
    name = re.sub(r"[^a-z0-9\-]", "", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-")[:64]

def ensure_render_service(project_name: str, component_name: str, repo_url: str, runtime: str, root_dir: str, install_command: str, start_command: str, env_vars: dict, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    safe_name = sanitize_render_name(f"{project_name}-{component_name}")

    # 1. Fetch the owner ID
    owners_resp = requests.get("https://api.render.com/v1/owners", headers=headers)
    owners_resp.raise_for_status()
    owners = owners_resp.json()
    if not owners:
        raise Exception("No Render workspace owner found for this API key.")
    owner_id = owners[0]["owner"]["id"]

    # 2. Check if service already exists
    svc_list_resp = requests.get(f"https://api.render.com/v1/services?name={safe_name}", headers=headers)
    svc_list_resp.raise_for_status()
    for item in svc_list_resp.json():
        if item.get("service", {}).get("name") == safe_name:
            return item["service"]["id"]
            
    # 3. Create the service from scratch
    repo_full_url = f"https://github.com/{repo_url}" if not repo_url.startswith("http") else repo_url
    
    # Render env defaults to python/node etc based on spec
    if runtime == "nodejs": runtime = "node"
    
    render_envs = [{"key": k, "value": str(v)} for k, v in env_vars.items()]
    
    payload = {
        "type": "web_service",
        "name": safe_name,
        "ownerId": owner_id,
        "repo": repo_full_url,
        "autoDeploy": "no",
        "envVars": render_envs,
        "serviceDetails": {
            "env": runtime,
            "envSpecificDetails": {
                "buildCommand": install_command or "",
                "startCommand": start_command or ""
            }
        }
    }
    if root_dir:
        payload["rootDir"] = root_dir
        
    create_resp = requests.post("https://api.render.com/v1/services", headers=headers, json=payload)
    if not create_resp.ok:
        try:
            err_msg = create_resp.json()
            if "repo" in str(err_msg).lower() or "github" in str(err_msg).lower():
                raise Exception(
                    f"Render GitHub Integration missing or no access. Please install the Render GitHub App on your GitHub account "
                    f"and grant it access to the repository '{repo_url}'. Then strictly try deploying again."
                )
        except Exception as e:
            if "Render GitHub Integration missing" in str(e):
                raise e
        raise Exception(f"Failed to create Render service [{create_resp.status_code}]: {create_resp.text}")

    return create_resp.json()["id"]

def trigger_render_deploy(service_id: str, api_key: str): 
    url = f"https://api.render.com/v1/services/{service_id}/deploys"
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_render_service_url(service_id: str, api_key: str): 
    url = f"https://api.render.com/v1/services/{service_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("serviceDetails", {}).get("url")