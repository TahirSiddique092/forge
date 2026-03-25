import requests

def trigger_vercel_deploy(project_name: str, repo_url: str, env_vars: dict, token: str): # Added token param
    url = "https://api.vercel.com/v13/deployments"
    headers = {"Authorization": f"Bearer {token}"}
    
    vercel_envs = [{"key": k, "value": v, "type": "encrypted"} for k, v in env_vars.items()]

    payload = {
        "name": project_name,
        "gitSource": {
            "type": "github",
            "repo": repo_url,
            "ref": "main"
        },
        "env": vercel_envs
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()