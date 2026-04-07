import jwt
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY").replace('\\n', '\n')

def get_app_jwt():
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": int(GITHUB_APP_ID),
    }
    return jwt.encode(payload, GITHUB_PRIVATE_KEY, algorithm="RS256")


def get_installation_token(installation_id: int) -> str:
    jwt_token = get_app_jwt()

    res = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        },
    )
    
    if res.status_code != 201:
        print(f"GitHub API Error: {res.status_code} - {res.text}") 
        res.raise_for_status()

    res.raise_for_status()
    return res.json()["token"]
