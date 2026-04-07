import jwt
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")

SECRET_FILE_PATH = "/etc/secrets/github_private_key.pem"

def get_private_key():
    if os.path.exists(SECRET_FILE_PATH):
        with open(SECRET_FILE_PATH, "r") as f:
            return f.read().strip()
    
    key = os.getenv("GITHUB_PRIVATE_KEY", "")
    return key.replace('\\n', '\n').strip()

def get_app_jwt():
    private_key = get_private_key()
    
    if not private_key or not GITHUB_APP_ID:
        print("CRITICAL: GitHub credentials missing!", flush=True)
        return None

    now = int(time.time())
    payload = {
        "iat": now - 60,         
        "exp": now + (5 * 60),     
        "iss": int(GITHUB_APP_ID),
    }
    
    token = jwt.encode(payload, private_key, algorithm="RS256")
    
    if isinstance(token, bytes):
        token = token.decode('utf-8')
        
    return token.strip()

def get_installation_token(installation_id: int) -> str:
    jwt_token = get_app_jwt()

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    res = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers=headers,
    )
    
    if res.status_code != 201:
        print(f"GitHub API Error: {res.status_code} - {res.text}", flush=True) 
        res.raise_for_status()

    return res.json()["token"]