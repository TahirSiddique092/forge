import requests
import os

VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
VERCEL_TEAM_ID = os.getenv("VERCEL_TEAM_ID") # Optional, if using teams

def trigger_vercel_deploy(project_name: str, repo_url: str, env_vars: dict):
    """
    Triggers a Vercel deployment and injects dynamic environment variables.
    """
    url = "https://api.vercel.com/v13/deployments"
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    # Convert Forge env_vars to Vercel format
    vercel_envs = [
        {"key": k, "value": v, "type": "encrypted"} 
        for k, v in env_vars.items()
    ]

    payload = {
        "name": project_name,
        "gitSource": {
            "type": "github",
            "repo": repo_url,
            "ref": "main" # Or the current commit SHA
        },
        "env": vercel_envs
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()