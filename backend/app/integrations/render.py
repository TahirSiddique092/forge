import requests
import os

RENDER_API_KEY = os.getenv("RENDER_API_KEY")

def trigger_render_deploy(service_id: str):
    """
    Triggers a manual deploy on Render for a specific service.
    """
    url = f"https://api.render.com/v1/services/{service_id}/deploys"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_render_service_url(service_id: str):
    """
    Fetches the live URL of the Render service.
    """
    url = f"https://api.render.com/v1/services/{service_id}"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("serviceDetails", {}).get("url")