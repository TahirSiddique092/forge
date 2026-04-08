import requests

VERCEL_API = "https://api.vercel.com"


def ensure_vercel_project(project_name: str, repo_full_name: str, token: str):
    """
    Creates the Vercel project if it doesn't already exist.
    repo_full_name should be "owner/repo" format.
    Safe to call on every deploy — a 409 (already exists) is silently ignored.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": project_name,
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
        raise Exception(
            f"Failed to create Vercel project '{project_name}' "
            f"({response.status_code}): {response.text}"
        )


def trigger_vercel_deploy(project_name: str, repo_url: str, env_vars: dict, token: str):
    """
    Triggers a production deployment for an existing Vercel project.
    repo_url can be "owner/repo" or a full GitHub URL.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    vercel_envs = [{"key": k, "value": v, "type": "plain"} for k, v in env_vars.items()]

    repo_full_url = f"https://github.com/{repo_url}" if not repo_url.startswith("http") else repo_url

    payload = {
        "name": project_name,
        "project": project_name,
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
        raise Exception(
            f"Vercel deploy failed ({response.status_code}): {response.text}"
        )

    return response.json()