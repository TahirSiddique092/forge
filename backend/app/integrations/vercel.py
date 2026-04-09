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
                link = err_dict.get("link", "https://github.com/apps/vercel")
                repo = err_dict.get("repo", repo_full_name)
                raise Exception(
                    f"Vercel GitHub Integration missing. Please install the Vercel GitHub App at {link} "
                    f"and grant it access to the repository '{repo_full_name}'. Then try deploying again."
                )
        except Exception as e:
            if "Vercel GitHub Integration missing" in str(e):
                raise e # Re-raise our beautifully formatted error
        
        raise Exception(
            f"Failed to create Vercel project '{safe_name}' "
            f"({response.status_code}): {response.text}"
        )

def trigger_vercel_deploy(project_name: str, repo_url: str, env_vars: dict, token: str):
    """
    Triggers a production deployment for an existing Vercel project.
    repo_url can be "owner/repo" or a full GitHub URL.
    """
    safe_name = sanitize_vercel_name(project_name)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    vercel_envs = [{"key": k, "value": v, "type": "plain"} for k, v in env_vars.items()]

    repo_full_url = f"https://github.com/{repo_url}" if not repo_url.startswith("http") else repo_url

    payload = {
        "name": safe_name,
        "project": safe_name,
        "target": "production",
        "gitSource": {
            "type": "github",
            "repoUrl": repo_full_url,
            "ref": "main",
        },
        "env": vercel_envs,
    }

    response = requests.post(f"{VERCEL_API}/v13/deployments", headers=headers, json=payload)

    if not response.ok:
        try:
            error_data = response.json()
            err_dict = error_data.get("error", {})
            if err_dict.get("code") == "bad_request" and "install the GitHub integration first" in err_dict.get("message", ""):
                link = err_dict.get("link", "https://github.com/apps/vercel")
                raise Exception(
                    f"Vercel GitHub Integration missing. Please install the Vercel GitHub App at {link} "
                    f"and grant it access to the repository '{repo_url}'. Then try deploying again."
                )
        except Exception as e:
            if "Vercel GitHub Integration missing" in str(e):
                raise e
                
        raise Exception(
            f"Vercel deploy failed ({response.status_code}): {response.text}"
        )

    return response.json()