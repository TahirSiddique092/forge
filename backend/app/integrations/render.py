import requests

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