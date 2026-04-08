import requests

def trigger_vercel_deploy(project_name: str, repo_url: str, env_vars: dict, token: str):
    url = "https://api.vercel.com/v13/deployments"
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

    response = requests.post(url, headers=headers, json=payload)

    if not response.ok:
        raise Exception(
            f"Vercel deploy failed ({response.status_code}): {response.text}"
        )

    return response.json()