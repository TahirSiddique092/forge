import re
import requests

VERCEL_API = "https://api.vercel.com"


def sanitize_vercel_name(name: str) -> str:
    """
    Converts an arbitrary project name into a valid Vercel project name:
    - Lowercase
    - Spaces and underscores become hyphens
    - Any character that isn't a letter, digit, '.', '_', or '-' is removed
    - Collapse sequences of multiple hyphens into one
    - Strip leading/trailing hyphens
    """
    name = name.lower()
    name = name.replace(" ", "-").replace("_", "-")
    name = re.sub(r"[^a-z0-9.\-]", "", name)
    name = re.sub(r"-{2,}", "-", name)  # no '---' or '--'
    name = name.strip("-")
    return name


def ensure_vercel_project(project_name: str, repo_full_name: str, token: str):
    """
    Creates the Vercel project if it doesn't already exist.
    repo_full_name should be "owner/repo" format.
    Safe to call on every deploy — a 409 (already exists) is silently ignored.
    """
    safe_name = sanitize_vercel_name(project_name)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": safe_name,
        "gitRepository": {
            "type": "github",
            "repo": repo_full_name,
        },
    }

    response = requests.post(f"{VERCEL_API}/v9/projects", headers=headers, json=payload)

    if response.status_code == 409:
        # Project already exists — that's fine
        return

    if not response.ok:
        try:
            error_data = response.json()
            err_dict = error_data.get("error", {})
            if err_dict.get("code") == "bad_request" and "install the GitHub integration first" in err_dict.get("message", ""):
                raise Exception(f"GITHUB_INTEGRATION_MISSING: vercel | {repo_full_name}")
        except Exception as e:
            if "GITHUB_INTEGRATION_MISSING" in str(e):
                raise e
        
        raise Exception(f"Vercel project creation failed: {response.text}")

def trigger_vercel_deploy(project_name: str, repo_url: str, env_vars: dict, token: str, root_dir: str = None, build_command: str = None, install_command: str = None):
    """
    Triggers a production deployment for an existing Vercel project.
    repo_url can be "owner/repo" or a full GitHub URL.
    """
    safe_name = sanitize_vercel_name(project_name)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    # Fetch Vercel project details to get the linked repoId
    proj_resp = requests.get(f"{VERCEL_API}/v9/projects/{safe_name}", headers=headers)
    if not proj_resp.ok:
        raise Exception(f"Failed to fetch Vercel project details to retrieve repoId: {proj_resp.text}")
    
    proj_data = proj_resp.json()
    repo_id = proj_data.get("link", {}).get("repoId")
    
    # Fallback to GitHub public API if repoId isn't on the Vercel project object
    if not repo_id:
        repo_parts = repo_url.replace("https://github.com/", "").split("/")[-2:]
        if len(repo_parts) == 2:
            owner, repo = repo_parts[0], repo_parts[1].replace(".git", "")
            gh_resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}")
            if gh_resp.ok:
                repo_id = gh_resp.json().get("id")

    if not repo_id:
        raise Exception("Vercel could not determine the GitHub repoId. Ensure the repository is correctly linked and the Vercel GitHub Integration is fully installed.")

    vercel_envs = {str(k): str(v) for k, v in env_vars.items()}

    payload = {
        "name": safe_name,
        "project": safe_name,
        "target": "production",
        "gitSource": {
            "type": "github",
            "repoId": repo_id,
            "ref": "main",
        },
        "env": vercel_envs,
        "projectSettings": {}
    }
    
    if root_dir:
        payload["projectSettings"]["rootDirectory"] = root_dir
    if build_command:
        payload["projectSettings"]["buildCommand"] = build_command
    if install_command:
        payload["projectSettings"]["installCommand"] = install_command
        
    if not payload["projectSettings"]:
        del payload["projectSettings"]

    response = requests.post(f"{VERCEL_API}/v13/deployments", headers=headers, json=payload)

    if not response.ok:
        try:
            error_data = response.json()
            err_dict = error_data.get("error", {})
            if err_dict.get("code") == "bad_request" and "install the GitHub integration first" in err_dict.get("message", ""):
                raise Exception(f"GITHUB_INTEGRATION_MISSING: vercel | {repo_url}")
        except Exception as e:
            if "GITHUB_INTEGRATION_MISSING" in str(e):
                raise e
                
        raise Exception(
            f"Vercel deploy failed ({response.status_code}): {response.text}"
        )

    res_json = response.json()
    aliases = res_json.get("alias", [])
    if aliases:
        # Vercel provides project aliases, use the first one if available to show the nice domain
        res_json["url"] = aliases[0]
        
    return res_json